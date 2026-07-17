"""Chat service integration: real Postgres, respx-mocked provider."""

from pathlib import Path

import httpx
import pytest
import respx

from octo import chat
from octo.config import settings
from octo.providers.openrouter import PaidModelRefused
from octo.registry import load_registry

REPO_AGENTS = Path(__file__).resolve().parents[2] / "agents"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"


@pytest.fixture
def registry():
    return load_registry(REPO_AGENTS)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")


def mock_reply(text="hello there", usage=None):
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": text}}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


@respx.mock
async def test_full_conversation_roundtrip(pool, registry):
    respx.post(OR_URL).mock(return_value=mock_reply())
    convo = await chat.create_conversation(pool)
    assert convo["persona"] == "chat-assistant"

    reply = await chat.send(pool, registry, str(convo["id"]), "hi, who are you?")
    assert reply["role"] == "assistant"
    assert reply["content"] == "hello there"
    assert reply["prompt_tokens"] == 10

    msgs = await chat.get_messages(pool, str(convo["id"]))
    assert [m["role"] for m in msgs] == ["user", "assistant"]

    # auto-title from first user message; updated_at maintained
    convo2 = await chat.get_conversation(pool, str(convo["id"]))
    assert convo2["title"] == "hi, who are you?"
    assert convo2["updated_at"] >= convo["updated_at"]


@respx.mock
async def test_persona_prompt_reaches_provider(pool, registry):
    route = respx.post(OR_URL).mock(return_value=mock_reply())
    convo = await chat.create_conversation(pool)
    await chat.send(pool, registry, str(convo["id"]), "hello")
    import json

    sent = json.loads(route.calls[0].request.content)
    assert sent["messages"][0]["role"] == "system"
    assert "research assistant" in sent["messages"][0]["content"]


async def test_paid_model_refused_before_any_write_of_reply(pool, registry):
    convo = await chat.create_conversation(pool, model="anthropic/claude-sonnet-5")
    with pytest.raises(PaidModelRefused):
        await chat.send(pool, registry, str(convo["id"]), "hi")


async def test_delete_cascades(pool, registry):
    convo = await chat.create_conversation(pool)
    await chat._append(pool, str(convo["id"]), "user", "orphan-to-be")
    assert await chat.delete_conversation(pool, str(convo["id"])) is True
    assert await chat.get_messages(pool, str(convo["id"])) == []


def test_sliding_window_keeps_system_and_tail():
    history = [
        {"role": "user", "content": "x" * 4000, "prompt_tokens": 1000},
        {"role": "assistant", "content": "y" * 4000, "prompt_tokens": 1000},
        {"role": "user", "content": "recent question", "prompt_tokens": 5},
    ]
    ctx = chat.build_context("system prompt", history, budget=1100)
    assert ctx[0]["role"] == "system"
    contents = [m["content"] for m in ctx[1:]]
    assert "recent question" in contents  # tail always survives
    assert "x" * 4000 not in contents  # oldest trimmed
    # everything fits when budget is large
    ctx_full = chat.build_context("system prompt", history, budget=100_000)
    assert len(ctx_full) == 4


@respx.mock
async def test_unknown_conversation_raises(pool, registry):
    with pytest.raises(LookupError):
        await chat.send(pool, registry, "00000000-0000-0000-0000-000000000000", "hi")


@respx.mock
async def test_usage_today_counts(pool, registry):
    respx.post(OR_URL).mock(return_value=mock_reply())
    convo = await chat.create_conversation(pool)
    await chat.send(pool, registry, str(convo["id"]), "one")
    usage = await chat.usage_today(pool)
    assert usage["native_requests_today"] == 1
    assert usage["free_tier_daily_limit"] == 50
