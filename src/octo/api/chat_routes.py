"""Native chat API — the spine-owned, stateful chat surface (ADR-0007).

Streaming uses ONE dialect everywhere: OpenAI-style chat.completion.chunk SSE events,
plus a final custom event carrying the persisted message id — so the CLI, Telegram (P3),
and the dashboard (P6) all parse the same format as /v1."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from octo import chat
from octo.api.auth import require_chat_token
from octo.providers.ollama import OllamaUnavailable
from octo.providers.openrouter import PaidModelRefused, ProviderError, QuotaExceeded

log = logging.getLogger("octo.api.chat")

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_chat_token)])


def _pool(request: Request):
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    return pool


class ConversationRequest(BaseModel):
    model: str = "default"
    persona: str | None = None


@router.post("/conversations", status_code=201)
async def create_conversation(body: ConversationRequest, request: Request):
    if body.persona and body.persona not in request.app.state.registry:
        raise HTTPException(status_code=404, detail=f"unknown persona '{body.persona}'")
    return await chat.create_conversation(_pool(request), model=body.model, persona=body.persona)


@router.get("/conversations")
async def list_conversations(request: Request, limit: int = 50):
    return await chat.list_conversations(_pool(request), limit=min(limit, 200))


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    convo = await chat.get_conversation(_pool(request), conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return convo


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, request: Request):
    return await chat.get_messages(_pool(request), conversation_id)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    if not await chat.delete_conversation(_pool(request), conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"deleted": conversation_id}


class MessageRequest(BaseModel):
    content: str
    stream: bool = False
    tags: dict = {}  # caller categories for data analysis (ADR-0008)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, body: MessageRequest, request: Request):
    pool = _pool(request)
    registry = request.app.state.registry
    try:
        if not body.stream:
            return await chat.send(pool, registry, conversation_id, body.content, tags=body.tags)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PaidModelRefused, OllamaUnavailable) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (ProviderError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    async def sse():
        try:
            async for chunk in chat.send_stream(
                pool, registry, conversation_id, body.content, tags=body.tags
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:  # response already committed — emit a readable
            # error event instead of cutting the stream mid-chunk
            log.warning("chat stream failed: %s", exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


@router.get("/usage")
async def usage(request: Request):
    return await chat.usage_today(_pool(request))
