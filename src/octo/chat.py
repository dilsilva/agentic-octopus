"""Chat service — the UI-independent core (ADR-0007).

Conversations and messages live in the spine's Postgres; the native API, the CLI,
and any future surface call these functions. Provider access goes through the
ChatProvider seam; the :free cost guard applies (OpenRouter policy).
"""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from octo.config import settings
from octo.providers.base import get_chat_provider
from octo.providers.openrouter import enforce_free
from octo.registry import LoadedAgent

DEFAULT_PERSONA = "chat-assistant"
FALLBACK_SYSTEM_PROMPT = (
    "You are a helpful research assistant. Be accurate, cite what you know and what "
    "you don't, and state your knowledge cutoff when asked about recent events."
)
TITLE_MAX = 40


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# --- conversation CRUD ------------------------------------------------------


async def create_conversation(
    pool: AsyncConnectionPool, *, model: str = "default", persona: str | None = None
) -> dict[str, Any]:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "INSERT INTO conversations (model, persona) VALUES (%s, %s) RETURNING *",
            (model, persona or DEFAULT_PERSONA),
        )
        return await cur.fetchone()


async def list_conversations(pool: AsyncConnectionPool, limit: int = 50) -> list[dict[str, Any]]:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT c.*, (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) "
            "AS message_count FROM conversations c ORDER BY updated_at DESC LIMIT %s",
            (limit,),
        )
        return await cur.fetchall()


async def get_conversation(pool: AsyncConnectionPool, conversation_id: str) -> dict | None:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT * FROM conversations WHERE id = %s", (conversation_id,))
        return await cur.fetchone()


async def get_messages(pool: AsyncConnectionPool, conversation_id: str) -> list[dict[str, Any]]:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT * FROM messages WHERE conversation_id = %s ORDER BY id",
            (conversation_id,),
        )
        return await cur.fetchall()


async def delete_conversation(pool: AsyncConnectionPool, conversation_id: str) -> bool:
    async with pool.connection() as conn:
        cur = await conn.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
        return cur.rowcount == 1


# --- sending ----------------------------------------------------------------


def system_prompt_for(persona: str | None, registry: dict[str, LoadedAgent]) -> str:
    agent = registry.get(persona or DEFAULT_PERSONA)
    return agent.prompt if agent else FALLBACK_SYSTEM_PROMPT


def build_context(
    system_prompt: str, history: list[dict[str, Any]], budget: int | None = None
) -> list[dict[str, str]]:
    """Token-budget sliding window: system prompt + the most recent messages that fit.
    Long conversations degrade gracefully instead of overflowing model context."""
    budget = budget or settings.chat_context_budget
    remaining = budget - estimate_tokens(system_prompt)
    kept: list[dict[str, str]] = []
    for msg in reversed(history):  # newest first, so the tail always survives
        cost = msg.get("prompt_tokens") or estimate_tokens(msg["content"])
        if remaining - cost < 0 and kept:
            break
        remaining -= cost
        kept.append({"role": msg["role"], "content": msg["content"]})
    kept.reverse()
    return [{"role": "system", "content": system_prompt}, *kept]


async def _append(
    pool: AsyncConnectionPool, conversation_id: str, role: str, content: str, **fields: Any
) -> dict[str, Any]:
    cols = ["conversation_id", "role", "content"]
    vals: list[Any] = [conversation_id, role, content]
    for k, v in fields.items():
        cols.append(k)
        vals.append(Jsonb(v) if k == "metadata" else v)
    placeholders = ", ".join(["%s"] * len(cols))
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            f"INSERT INTO messages ({', '.join(cols)}) VALUES ({placeholders}) RETURNING *",  # noqa: S608
            vals,
        )
        msg = await cur.fetchone()
        await conn.execute(
            "UPDATE conversations SET updated_at = now(), "
            "title = COALESCE(title, %s) WHERE id = %s",
            (content[:TITLE_MAX] if role == "user" else None, conversation_id),
        )
        return msg


async def _prepare(
    pool: AsyncConnectionPool,
    registry: dict[str, LoadedAgent],
    conversation_id: str,
    user_text: str,
) -> tuple[str, list[dict[str, str]]]:
    """Shared preamble for send/send_stream: persist user msg, build payload context."""
    convo = await get_conversation(pool, conversation_id)
    if convo is None:
        raise LookupError(f"conversation {conversation_id} not found")
    provider = get_chat_provider(settings.chat_provider)
    model = provider.resolve_model(convo["model"] or "default")
    enforce_free(model)  # OpenRouter billing policy (cost guard)
    await _append(pool, conversation_id, "user", user_text)
    history = await get_messages(pool, conversation_id)
    context = build_context(system_prompt_for(convo["persona"], registry), history)
    return model, context


async def send(
    pool: AsyncConnectionPool,
    registry: dict[str, LoadedAgent],
    conversation_id: str,
    user_text: str,
) -> dict[str, Any]:
    model, context = await _prepare(pool, registry, conversation_id, user_text)
    provider = get_chat_provider(settings.chat_provider)
    started = time.monotonic()
    r = await provider.complete({"model": model, "messages": context})
    duration_ms = int((time.monotonic() - started) * 1000)
    if r.status_code != 200:
        raise RuntimeError(f"provider error {r.status_code}: {r.text[:300]}")
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"provider error: {str(data['error'])[:300]}")
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return await _append(
        pool,
        conversation_id,
        "assistant",
        content,
        model=model,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        duration_ms=duration_ms,
    )


async def send_stream(
    pool: AsyncConnectionPool,
    registry: dict[str, LoadedAgent],
    conversation_id: str,
    user_text: str,
) -> AsyncIterator[dict[str, Any]]:
    """Yields OpenAI-style chunk dicts; final yield is {"done": ..., "message": row}.
    If the client disconnects mid-stream, the partial reply is persisted with
    metadata.truncated = true (the generator's finally block runs on aclose())."""
    model, context = await _prepare(pool, registry, conversation_id, user_text)
    provider = get_chat_provider(settings.chat_provider)
    started = time.monotonic()
    parts: list[str] = []
    usage: dict[str, Any] = {}
    completed = False
    try:
        async with provider.stream({"model": model, "messages": context}) as chunks:
            buffer = b""
            async for raw in chunks:
                buffer += raw
                while b"\n\n" in buffer:
                    event, buffer = buffer.split(b"\n\n", 1)
                    for line in event.split(b"\n"):
                        if not line.startswith(b"data: "):
                            continue
                        payload = line[6:].strip()
                        if payload == b"[DONE]":
                            continue
                        chunk = json.loads(payload)
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                        if delta.get("content"):
                            parts.append(delta["content"])
                        yield chunk
        completed = True
    finally:
        content = "".join(parts)
        if content:
            msg = await _append(
                pool,
                conversation_id,
                "assistant",
                content,
                model=model,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                duration_ms=int((time.monotonic() - started) * 1000),
                metadata={} if completed else {"truncated": True},
            )
            if completed:
                yield {"done": True, "message_id": msg["id"], "usage": usage}


async def usage_today(pool: AsyncConnectionPool) -> dict[str, Any]:
    """Rough free-tier burn visibility: today's provider requests from both surfaces."""
    async with pool.connection() as conn:
        native = await (
            await conn.execute(
                "SELECT count(*) FROM messages WHERE role = 'assistant' "
                "AND created_at >= date_trunc('day', now())"
            )
        ).fetchone()
        shim = await (
            await conn.execute(
                "SELECT count(*) FROM chat_completions WHERE ts >= date_trunc('day', now())"
            )
        ).fetchone()
    return {
        "native_requests_today": native[0],
        "openai_compat_requests_today": shim[0],
        "free_tier_daily_limit": 50,
    }
