"""Chat service — the UI-independent core (ADR-0007).

Conversations and messages live in the spine's Postgres; the native API, the CLI,
and any future surface call these functions. Provider access goes through the
ChatProvider seam; the :free cost guard applies (OpenRouter policy).

Tool loop (ADR-0007 fast-follow): personas whose manifest lists core tools
(web_search, fetch_page) get a PROMPTED tool protocol — model-agnostic, so it works
with whatever :free model the router picks (most have no native function calling).
The model emits a `TOOL_CALL {json}` line; the service executes, records an
audit row (role='tool'), feeds results back, and loops (bounded by
CHAT_MAX_TOOL_CALLS). Every surface gets search — never only a UI container.
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from octo.config import settings
from octo.providers.base import route_chat_model
from octo.providers.openrouter import AUTO_MODEL
from octo.registry import LoadedAgent
from octo.telemetry import llm_span, merge_tags
from octo.tools import TOOL_REGISTRY, run_tool

log = logging.getLogger("octo.chat")

DEFAULT_PERSONA = "chat-assistant"
FALLBACK_SYSTEM_PROMPT = (
    "You are a helpful research assistant. Be accurate, cite what you know and what "
    "you don't, and state your knowledge cutoff when asked about recent events."
)
TITLE_MAX = 40
TOOL_MARKER = "TOOL_CALL"
TOOL_RESULT_MAX_CHARS = 4000


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def routed_model_prefix(requested_model: str, actual_model: str) -> str:
    """`[actual-model]` lead-in when smart routing picked the model — the operator
    always sees WHO answered (per Diego, 2026-07-19)."""
    if settings.chat_show_routed_model and requested_model == AUTO_MODEL and actual_model:
        return f"`[{actual_model}]`\n\n"
    return ""


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


# --- tool protocol ----------------------------------------------------------


def tools_for(persona: str | None, registry: dict[str, LoadedAgent]) -> list[str]:
    """Core tools this persona may use: manifest.tools ∩ TOOL_REGISTRY."""
    if not settings.chat_tools_enabled:
        return []
    agent = registry.get(persona or DEFAULT_PERSONA)
    if agent is None:
        return []
    return [t for t in agent.manifest.tools if t in TOOL_REGISTRY]


def tool_protocol_prompt(tool_names: list[str]) -> str:
    lines = [
        "\n\n## Tools",
        "You can use tools for anything recent, factual, or verifiable. To call one,",
        "reply with ONLY a single line (no other text):",
        'TOOL_CALL {"tool": "<name>", "args": {...}}',
        "Available tools:",
    ]
    for name in tool_names:
        lines.append(f"- {name}: {TOOL_REGISTRY[name]['description']}")
    lines += [
        f"You may chain up to {settings.chat_max_tool_calls} calls, one at a time.",
        "After receiving results, either call another tool or give your final answer.",
        "Final answers based on tool results MUST cite source URLs inline.",
        "If tools fail, say so and answer from your knowledge, clearly labeled.",
    ]
    return "\n".join(lines)


def parse_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """Detect the prompted-protocol marker and extract (tool, args). Lenient:
    the marker line may appear anywhere; the first one wins."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(TOOL_MARKER):
            continue
        payload = line[len(TOOL_MARKER) :].strip()
        try:
            data = json.loads(payload)
            return str(data["tool"]), dict(data.get("args") or {})
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
    return None


# --- context building -------------------------------------------------------


def system_prompt_for(persona: str | None, registry: dict[str, LoadedAgent]) -> str:
    agent = registry.get(persona or DEFAULT_PERSONA)
    base = agent.prompt if agent else FALLBACK_SYSTEM_PROMPT
    tool_names = tools_for(persona, registry)
    return base + tool_protocol_prompt(tool_names) if tool_names else base


def build_context(
    system_prompt: str, history: list[dict[str, Any]], budget: int | None = None
) -> list[dict[str, str]]:
    """Token-budget sliding window: system prompt + the most recent messages that fit.
    role='tool' rows are audit-only and excluded (their substance lives in the
    assistant answers that follow them)."""
    budget = budget or settings.chat_context_budget
    remaining = budget - estimate_tokens(system_prompt)
    kept: list[dict[str, str]] = []
    for msg in reversed(history):  # newest first, so the tail always survives
        if msg["role"] == "tool":
            continue
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
        vals.append(Jsonb(v) if k in ("metadata", "tags") else v)
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
) -> tuple[str, list[dict[str, str]], list[str]]:
    """Shared preamble: persist user msg, build payload context, resolve tools."""
    convo = await get_conversation(pool, conversation_id)
    if convo is None:
        raise LookupError(f"conversation {conversation_id} not found")
    # one routing seam for every surface: octo/local-* -> ollama, octo/claude ->
    # anthropic (key-gated), everything else -> chat_provider under the :free guard
    provider, model, provider_name = await route_chat_model(convo["model"] or "default")
    await _append(pool, conversation_id, "user", user_text)
    history = await get_messages(pool, conversation_id)
    context = build_context(system_prompt_for(convo["persona"], registry), history)
    return (
        provider,
        provider_name,
        model,
        context,
        tools_for(convo["persona"], registry),
        convo["persona"],
    )


async def _execute_tool_round(
    pool: AsyncConnectionPool,
    conversation_id: str,
    context: list[dict[str, str]],
    assistant_text: str,
    tool: str,
    args: dict[str, Any],
    allowed: list[str],
) -> None:
    """Run one tool call, persist the audit row, extend the context in place."""
    result = (
        await run_tool(tool, args)
        if tool in allowed
        else {"error": f"tool '{tool}' not enabled for this persona"}
    )
    result_json = json.dumps(result, default=str)[:TOOL_RESULT_MAX_CHARS]
    await _append(
        pool,
        conversation_id,
        "tool",
        f"{tool}({json.dumps(args, default=str)[:500]})",
        metadata={"call": {"tool": tool, "args": args}, "result": json.loads(result_json)},
    )
    # tool messages travel as user role — :free models have no native tool role
    context.append({"role": "assistant", "content": assistant_text})
    context.append(
        {
            "role": "user",
            "content": (
                f"[tool result: {tool}]\n{result_json}\n"
                "Use this. Cite source URLs in your answer. "
                "Call another tool only if you still need more information."
            ),
        }
    )


async def send(
    pool: AsyncConnectionPool,
    registry: dict[str, LoadedAgent],
    conversation_id: str,
    user_text: str,
    tags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider, provider_name, model, context, allowed_tools, persona = await _prepare(
        pool, registry, conversation_id, user_text
    )
    started = time.monotonic()
    usage: dict[str, Any] = {}
    actual_model = model
    content = ""
    all_tags = merge_tags(
        {
            "surface": "native",
            "provider": provider_name,
            "persona": persona,
            "conversation": conversation_id,
            "routed": model == AUTO_MODEL,
        },
        tags,
    )
    tool_rounds = 0
    async with llm_span(
        "chat", provider=provider_name, requested_model=model, tags=all_tags
    ) as obs:
        for round_no in range(settings.chat_max_tool_calls + 1):
            r = await provider.complete({"model": model, "messages": context})
            if r.status_code != 200:
                raise RuntimeError(f"provider error {r.status_code}: {r.text[:300]}")
            data = r.json()
            if data.get("error"):
                raise RuntimeError(f"provider error: {str(data['error'])[:300]}")
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or usage
            actual_model = data.get("model") or actual_model
            call = parse_tool_call(content) if allowed_tools else None
            if call is None or round_no >= settings.chat_max_tool_calls:
                break
            tool, args = call
            tool_rounds += 1
            log.info("chat %s tool round %d: %s(%s)", conversation_id, round_no + 1, tool, args)
            await _execute_tool_round(
                pool, conversation_id, context, content, tool, args, allowed_tools
            )
        obs.update(
            actual_model=actual_model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            tool_rounds=tool_rounds,
        )
    return await _append(
        pool,
        conversation_id,
        "assistant",
        routed_model_prefix(model, actual_model) + content,
        model=actual_model,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        duration_ms=int((time.monotonic() - started) * 1000),
        tags=all_tags,
    )


# --- streaming --------------------------------------------------------------


async def _iter_sse_deltas(chunks: AsyncIterator[bytes]) -> AsyncIterator[dict[str, Any]]:
    """Parse provider SSE into events: {'delta': str} | {'usage': {...}} | {'model': str}."""
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
                    return
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if chunk.get("usage"):
                    yield {"usage": chunk["usage"]}
                if chunk.get("model"):
                    yield {"model": chunk["model"]}
                delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                if delta.get("content"):
                    yield {"delta": delta["content"]}


def _chunk_event(text: str) -> dict[str, Any]:
    return {"object": "chat.completion.chunk", "choices": [{"delta": {"content": text}}]}


async def send_stream(
    pool: AsyncConnectionPool,
    registry: dict[str, LoadedAgent],
    conversation_id: str,
    user_text: str,
    tags: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Streams the final answer as OpenAI-style chunks; tool rounds surface as
    {'tool_status': ...} events. Detection trick: hold back the first few chars of
    each round — if they start with TOOL_CALL it's a tool round (never shown),
    otherwise flush and stream live. Partial replies on disconnect are persisted
    with metadata.truncated (the finally block runs on generator aclose())."""
    provider, provider_name, model, context, allowed_tools, persona = await _prepare(
        pool, registry, conversation_id, user_text
    )
    started = time.monotonic()
    all_tags = merge_tags(
        {
            "surface": "native",
            "provider": provider_name,
            "persona": persona,
            "conversation": conversation_id,
            "routed": model == AUTO_MODEL,
            "stream": True,
        },
        tags,
    )
    usage: dict[str, Any] = {}
    actual_model = [model]
    parts: list[str] = []
    completed = False
    prefix_done = False

    def _prefix_chunk() -> str:
        nonlocal prefix_done
        if prefix_done:
            return ""
        prefix_done = True
        p = routed_model_prefix(model, actual_model[0])
        if p:
            parts.append(p)
        return p

    try:
        for round_no in range(settings.chat_max_tool_calls + 1):
            held = ""
            decided = tool_round = False
            round_text: list[str] = []
            async with provider.stream({"model": model, "messages": context}) as chunks:
                async for ev in _iter_sse_deltas(chunks):
                    if "usage" in ev:
                        usage = ev["usage"]
                        continue
                    if "model" in ev:
                        actual_model[0] = ev["model"]
                        continue
                    text = ev["delta"]
                    round_text.append(text)
                    if decided:
                        if not tool_round:
                            parts.append(text)
                            yield _chunk_event(text)
                        continue
                    held += text
                    stripped = held.lstrip()
                    if len(stripped) >= len(TOOL_MARKER) or "\n" in held:
                        decided = True
                        tool_round = bool(allowed_tools) and stripped.startswith(TOOL_MARKER)
                        if not tool_round and held:
                            if p := _prefix_chunk():
                                yield _chunk_event(p)
                            parts.append(held)
                            yield _chunk_event(held)
            full_round = "".join(round_text)
            if not decided:  # very short response, decide now
                tool_round = bool(allowed_tools) and full_round.lstrip().startswith(TOOL_MARKER)
                if not tool_round and full_round:
                    if p := _prefix_chunk():
                        yield _chunk_event(p)
                    parts.append(full_round)
                    yield _chunk_event(full_round)
            if not tool_round:
                completed = True
                return
            call = parse_tool_call(full_round)
            if call is None or round_no >= settings.chat_max_tool_calls:
                # unparseable marker or budget exhausted: emit as-is, stop
                if p := _prefix_chunk():
                    yield _chunk_event(p)
                parts.append(full_round)
                yield _chunk_event(full_round)
                completed = True
                return
            tool, args = call
            yield {"tool_status": {"tool": tool, "args": args, "round": round_no + 1}}
            await _execute_tool_round(
                pool, conversation_id, context, full_round, tool, args, allowed_tools
            )
    finally:
        content = "".join(parts)
        if content:
            msg = await _append(
                pool,
                conversation_id,
                "assistant",
                content,
                model=actual_model[0],
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                duration_ms=int((time.monotonic() - started) * 1000),
                metadata={} if completed else {"truncated": True},
                tags=all_tags,
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
        tool_rounds = await (
            await conn.execute(
                "SELECT count(*) FROM messages WHERE role = 'tool' "
                "AND created_at >= date_trunc('day', now())"
            )
        ).fetchone()
        shim = await (
            await conn.execute(
                "SELECT count(*) FROM chat_completions WHERE ts >= date_trunc('day', now())"
            )
        ).fetchone()
    return {
        "native_requests_today": native[0] + tool_rounds[0],  # each tool round = a request
        "openai_compat_requests_today": shim[0],
        "free_tier_daily_limit": 50,
    }
