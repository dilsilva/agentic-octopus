"""octo/claude — Anthropic chat provider translation + routing (no real SDK calls)."""

from types import SimpleNamespace

import pytest

from octo.config import settings
from octo.providers import claude as clp
from octo.providers.base import route_chat_model
from octo.providers.claude import AnthropicChatProvider
from octo.providers.openrouter import AUTO_MODEL, OpenRouterProvider, PaidModelRefused


@pytest.fixture
def anthropic_on(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(settings, "anthropic_default_model", "claude-opus-4-8")


def test_to_anthropic_kwargs_folds_system_and_strips_sampling(anthropic_on):
    kwargs = clp.to_anthropic_kwargs(
        {
            "model": clp.CLAUDE_MODEL,
            "temperature": 0.7,
            "top_p": 0.9,
            "messages": [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {"role": "user", "content": "again"},
            ],
        }
    )
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["system"] == "be brief"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["max_tokens"] == 16000
    assert "temperature" not in kwargs and "top_p" not in kwargs
    assert [m["role"] for m in kwargs["messages"]] == ["user", "assistant", "user"]


def test_resolve_model(anthropic_on):
    assert clp.resolve_model("default") == "claude-opus-4-8"
    assert clp.resolve_model(clp.CLAUDE_MODEL) == "claude-opus-4-8"
    assert clp.resolve_model("claude-haiku-4-5") == "claude-haiku-4-5"


def _msg(stop_reason="end_turn", text="hey"):
    return SimpleNamespace(
        id="msg_1",
        model="claude-opus-4-8",
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


def test_to_openai_response_shape():
    data = clp.to_openai_response(_msg())
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "hey"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def test_to_openai_response_refusal_maps_to_content_filter():
    data = clp.to_openai_response(_msg(stop_reason="refusal", text=""))
    assert data["choices"][0]["finish_reason"] == "content_filter"


class FakeStream:
    """Duck-types the SDK message stream: iterable events + get_final_message()."""

    def __init__(self, events, final):
        self._events, self._final = events, final

    def __aiter__(self):
        async def gen():
            for e in self._events:
                yield e

        return gen()

    async def get_final_message(self):
        return self._final


async def test_sse_from_stream_emits_openai_chunks():
    events = [
        SimpleNamespace(type="message_start", message=SimpleNamespace(id="msg_9")),
        SimpleNamespace(
            type="content_block_delta", delta=SimpleNamespace(type="text_delta", text="he")
        ),
        SimpleNamespace(
            type="content_block_delta", delta=SimpleNamespace(type="text_delta", text="y")
        ),
    ]
    chunks = [b async for b in clp.sse_from_stream(FakeStream(events, _msg()), "claude-opus-4-8")]
    assert all(c.startswith(b"data: ") for c in chunks)
    assert chunks[-1] == b"data: [DONE]\n\n"
    joined = b"".join(chunks)
    assert b'"content": "he"' in joined and b'"content": "y"' in joined
    assert b'"finish_reason": "stop"' in joined and b'"prompt_tokens": 10' in joined
    assert b"msg_9" in joined


async def test_route_claude_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(PaidModelRefused):
        await route_chat_model(clp.CLAUDE_MODEL)


async def test_route_claude_with_key(anthropic_on):
    provider, model, name = await route_chat_model(clp.CLAUDE_MODEL)
    assert isinstance(provider, AnthropicChatProvider)
    assert model == "claude-opus-4-8"
    assert name == "anthropic"


async def test_route_default_goes_to_openrouter(monkeypatch):
    monkeypatch.setattr(settings, "chat_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_default_model", AUTO_MODEL)
    provider, model, name = await route_chat_model("default")
    assert isinstance(provider, OpenRouterProvider)
    assert model == AUTO_MODEL
    assert name == "openrouter"


async def test_route_still_enforces_free_guard(monkeypatch):
    monkeypatch.setattr(settings, "chat_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_allow_paid", False)
    with pytest.raises(PaidModelRefused):
        await route_chat_model("some/paid-model")


async def test_list_models_gated_on_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert await AnthropicChatProvider().list_models() == []
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    assert await AnthropicChatProvider().list_models() == [clp.CLAUDE_MODEL]
