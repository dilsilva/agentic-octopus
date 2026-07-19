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
from octo.providers.base import get_chat_provider, route_chat_model
from octo.providers.claude import CLAUDE_MODEL
from octo.providers.openrouter import AUTO_MODEL, PaidModelRefused, QuotaExceeded
from octo.telemetry import llm_span, merge_tags, parse_tags_header

log = logging.getLogger("octo.api.v1")

router = APIRouter(prefix="/v1", tags=["openai-compat"], dependencies=[Depends(require_chat_token)])


def _openai_error(status: int, message: str, err_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": err_type, "code": status}},
    )


async def _log_metadata(request: Request, *, model, usage, duration_ms, stream, tags=None) -> None:
    pool = request.app.state.pool
    if pool is None:
        return  # degrade gracefully — the shim still answers without a DB
    usage = usage or {}
    from psycopg.types.json import Jsonb

    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO chat_completions "
            "(model, prompt_tokens, completion_tokens, total_tokens, duration_ms, stream, tags) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                model,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("total_tokens"),
                duration_ms,
                stream,
                Jsonb(tags or {}),
            ),
        )


@router.get("/models")
async def list_models():
    provider = get_chat_provider(settings.chat_provider)
    # octo/auto first: the smart router — picks a healthy :free model automatically.
    # octo/claude appears only when ANTHROPIC_API_KEY is set (billable, opt-in).
    models = [AUTO_MODEL]
    if settings.anthropic_key_set:
        models.append(CLAUDE_MODEL)
    models.extend(await provider.list_models())
    return {"object": "list", "data": [{"id": m, "object": "model"} for m in models]}


@router.post("/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    try:
        provider, model = route_chat_model(body.get("model") or "default")
    except PaidModelRefused as exc:
        return _openai_error(400, str(exc), "invalid_request_error")
    body["model"] = model
    tags = merge_tags(
        {
            "surface": "openai-compat",
            "provider": settings.chat_provider,
            "routed": model == AUTO_MODEL,
        },
        parse_tags_header(request.headers.get("x-octo-tags")),
    )
    # Shim contract (ADR-0007): plain completions only. Clients like Open WebUI may
    # inject tools (e.g. get_current_timestamp); many :free models have no tool-capable
    # endpoint and OpenRouter then 404s. Tool use arrives with the core tool loop.
    stripped = [
        k
        for k in ("tools", "tool_choice", "functions", "function_call")
        if body.pop(k, None) is not None
    ]
    if stripped:
        log.info("stripped unsupported fields from /v1 request: %s", stripped)
    started = time.monotonic()

    if not body.get("stream"):
        async with llm_span(
            "openai_compat", provider=settings.chat_provider, requested_model=model, tags=tags
        ) as obs:
            try:
                r = await provider.complete(body)
            except QuotaExceeded as exc:
                obs["error"] = "quota"
                return _openai_error(429, str(exc), "rate_limit_error")
        duration_ms = int((time.monotonic() - started) * 1000)
        data = r.json()
        if r.status_code == 200 and model == AUTO_MODEL and settings.chat_show_routed_model:
            try:  # answer leads with who actually answered (smart routing is opaque otherwise)
                msg = data["choices"][0]["message"]
                msg["content"] = f"`[{data.get('model', '?')}]`\n\n{msg['content']}"
            except (KeyError, IndexError, TypeError):
                pass
        usage = data.get("usage") if r.status_code == 200 else None
        obs.update(
            actual_model=data.get("model"),
            prompt_tokens=(usage or {}).get("prompt_tokens"),
            completion_tokens=(usage or {}).get("completion_tokens"),
        )
        await _log_metadata(
            request,
            model=data.get("model") or model,  # actual routed model, not 'octo/auto'
            usage=usage,
            duration_ms=duration_ms,
            stream=False,
            tags=tags,
        )
        return JSONResponse(status_code=r.status_code, content=data)

    async def sse():
        usage = {}
        actual_model = [model]
        want_prefix = model == AUTO_MODEL and settings.chat_show_routed_model
        try:
            async with provider.stream(body) as chunks:
                buffer = b""
                async for raw in chunks:
                    buffer += raw
                    # passthrough; peek for usage/model, inject routed-model prefix once
                    while b"\n\n" in buffer:
                        event, buffer = buffer.split(b"\n\n", 1)
                        for line in event.split(b"\n"):
                            if line.startswith(b"data: ") and line[6:].strip() != b"[DONE]":
                                try:
                                    chunk = json.loads(line[6:])
                                    if chunk.get("usage"):
                                        usage.update(chunk["usage"])
                                    if chunk.get("model"):
                                        actual_model[0] = chunk["model"]
                                    delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                                    if want_prefix and delta.get("content"):
                                        delta["content"] = (
                                            f"`[{actual_model[0]}]`\n\n{delta['content']}"
                                        )
                                        event = b"data: " + json.dumps(chunk).encode()
                                        want_prefix = False
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
                model=actual_model[0],
                usage=usage,
                duration_ms=int((time.monotonic() - started) * 1000),
                stream=True,
                tags=tags,
            )

    return StreamingResponse(sse(), media_type="text/event-stream")
