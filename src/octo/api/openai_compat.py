"""OpenAI-compatible shim for protocol clients (Open WebUI, any OpenAI SDK).

/v1 is a PROTOCOL namespace, not a version of this API (ADR-0007). The shim is
stateless — protocol clients manage their own history and send it in full each call.
Only request METADATA is logged (chat_completions); never message content."""

import json
import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from octo.api.auth import require_chat_token
from octo.config import settings
from octo.providers.base import get_chat_provider
from octo.providers.openrouter import PaidModelRefused, QuotaExceeded, enforce_free

log = logging.getLogger("octo.api.v1")

router = APIRouter(prefix="/v1", dependencies=[Depends(require_chat_token)])


def _openai_error(status: int, message: str, err_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": err_type, "code": status}},
    )


async def _log_metadata(request: Request, *, model, usage, duration_ms, stream) -> None:
    pool = request.app.state.pool
    if pool is None:
        return  # degrade gracefully — the shim still answers without a DB
    usage = usage or {}
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO chat_completions "
            "(model, prompt_tokens, completion_tokens, total_tokens, duration_ms, stream) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                model,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("total_tokens"),
                duration_ms,
                stream,
            ),
        )


@router.get("/models")
async def list_models():
    provider = get_chat_provider(settings.chat_provider)
    models = await provider.list_models()
    return {"object": "list", "data": [{"id": m, "object": "model"} for m in models]}


@router.post("/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    provider = get_chat_provider(settings.chat_provider)
    model = provider.resolve_model(body.get("model") or "default")
    try:
        enforce_free(model)
    except PaidModelRefused as exc:
        return _openai_error(400, str(exc), "invalid_request_error")
    body["model"] = model
    started = time.monotonic()

    if not body.get("stream"):
        try:
            r = await provider.complete(body)
        except QuotaExceeded as exc:
            return _openai_error(429, str(exc), "rate_limit_error")
        duration_ms = int((time.monotonic() - started) * 1000)
        usage = r.json().get("usage") if r.status_code == 200 else None
        await _log_metadata(
            request, model=model, usage=usage, duration_ms=duration_ms, stream=False
        )
        return JSONResponse(status_code=r.status_code, content=r.json())

    async def sse():
        usage = {}
        try:
            async with provider.stream(body) as chunks:
                buffer = b""
                async for raw in chunks:
                    buffer += raw
                    # passthrough verbatim; peek for usage in parallel
                    while b"\n\n" in buffer:
                        event, buffer = buffer.split(b"\n\n", 1)
                        for line in event.split(b"\n"):
                            if line.startswith(b"data: ") and line[6:].strip() != b"[DONE]":
                                try:
                                    chunk = json.loads(line[6:])
                                    if chunk.get("usage"):
                                        usage.update(chunk["usage"])
                                except json.JSONDecodeError:
                                    pass
                        yield event + b"\n\n"
        except Exception as exc:  # stream already committed HTTP 200 — a raised
            # exception here would cut the connection mid-chunk (client sees a
            # TransferEncodingError); emit a readable SSE error + DONE instead.
            log.warning("stream to provider failed: %s", exc)
            yield f"data: {json.dumps({'error': {'message': str(exc)}})}\n\n".encode()
            yield b"data: [DONE]\n\n"
        finally:
            await _log_metadata(
                request,
                model=model,
                usage=usage,
                duration_ms=int((time.monotonic() - started) * 1000),
                stream=True,
            )

    return StreamingResponse(sse(), media_type="text/event-stream")
