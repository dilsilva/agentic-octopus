"""Anthropic chat provider — the 'octo/claude' virtual model.

Speaks the ChatProvider protocol (OpenAI chat-completions shapes in and out) but
calls the Anthropic Messages API through the official SDK, translating both ways.
Selecting octo/claude IS the paid opt-in: it only routes when ANTHROPIC_API_KEY
is set (route_chat_model refuses otherwise, same 400 path as the cost guard).
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anthropic
import httpx

from octo.config import settings

log = logging.getLogger("octo.providers.claude")

CLAUDE_MODEL = "octo/claude"

# Anthropic stop_reason → OpenAI finish_reason
_FINISH = {"end_turn": "stop", "max_tokens": "length", "refusal": "content_filter"}


def to_anthropic_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """OpenAI chat-completions payload → Messages API kwargs.

    System messages fold into `system`; sampling params are dropped (Opus 4.8
    rejects temperature/top_p/top_k); adaptive thinking is always on.
    """
    msgs = payload.get("messages") or []
    system = "\n\n".join(m["content"] for m in msgs if m.get("role") == "system")
    kwargs: dict[str, Any] = {
        "model": resolve_model(payload.get("model") or "default"),
        "max_tokens": payload.get("max_tokens") or 16000,
        "messages": [
            {"role": m["role"], "content": m["content"]}
            for m in msgs
            if m.get("role") in ("user", "assistant") and m.get("content")
        ],
        "thinking": {"type": "adaptive"},
    }
    if system:
        kwargs["system"] = system
    return kwargs


def resolve_model(model: str) -> str:
    return settings.anthropic_default_model if model in ("default", CLAUDE_MODEL) else model


def _usage(u: Any) -> dict[str, int]:
    prompt = getattr(u, "input_tokens", 0) or 0
    completion = getattr(u, "output_tokens", 0) or 0
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def to_openai_response(msg: Any) -> dict[str, Any]:
    """Messages API response → OpenAI chat.completion dict."""
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    return {
        "id": msg.id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": msg.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": _FINISH.get(msg.stop_reason, "stop"),
            }
        ],
        "usage": _usage(msg.usage),
    }


def _chunk(
    msg_id: str,
    model: str,
    delta: dict[str, Any],
    finish: str | None = None,
    usage: dict[str, int] | None = None,
) -> bytes:
    chunk: dict[str, Any] = {
        "id": msg_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    if usage:
        chunk["usage"] = usage
    return f"data: {json.dumps(chunk)}\n\n".encode()


async def sse_from_stream(stream: Any, model: str) -> AsyncIterator[bytes]:
    """Translate a Messages API event stream into OpenAI chunk SSE bytes."""
    msg_id = "chatcmpl-octo-claude"
    yield _chunk(msg_id, model, {"role": "assistant", "content": ""})
    async for event in stream:
        etype = getattr(event, "type", None)
        if etype == "message_start":
            msg_id = event.message.id
        elif etype == "content_block_delta" and getattr(event.delta, "type", None) == "text_delta":
            yield _chunk(msg_id, model, {"content": event.delta.text})
    final = await stream.get_final_message()
    yield _chunk(
        msg_id,
        model,
        {},
        finish=_FINISH.get(final.stop_reason, "stop"),
        usage=_usage(final.usage),
    )
    yield b"data: [DONE]\n\n"


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


class AnthropicChatProvider:
    def resolve_model(self, model: str) -> str:
        return resolve_model(model)

    async def complete(self, payload: dict[str, Any]) -> httpx.Response:
        kwargs = to_anthropic_kwargs(payload)
        try:
            msg = await _client().messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            return httpx.Response(
                exc.status_code,
                json={"error": {"message": str(exc.message), "code": exc.status_code}},
            )
        return httpx.Response(200, json=to_openai_response(msg))

    @asynccontextmanager
    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[AsyncIterator[bytes]]:
        kwargs = to_anthropic_kwargs(payload)
        async with _client().messages.stream(**kwargs) as s:
            yield sse_from_stream(s, kwargs["model"])

    async def list_models(self) -> list[str]:
        return [CLAUDE_MODEL] if settings.anthropic_key_set else []
