from pathlib import Path

import httpx
import pytest
import respx

from octo.config import settings
from octo.executor import OpenRouterExecutor
from octo.registry import AgentManifest, LoadedAgent

OR_URL = "https://openrouter.ai/api/v1/chat/completions"


def make_agent(**overrides) -> LoadedAgent:
    fields = {"name": "test-agent", "executor": "openrouter", "model": "some/model:free"}
    fields.update(overrides)
    manifest = AgentManifest(**fields)
    return LoadedAgent(manifest=manifest, prompt="you are a test agent", path=Path("."))


@pytest.fixture
def events():
    collected = []

    async def on_event(type_, payload):
        collected.append((type_, payload))

    return collected, on_event


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")


@respx.mock
async def test_success_writes_output_file(tmp_path, events, api_key):
    collected, on_event = events
    respx.post(OR_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "# Brief\n\nhello world"}}],
                "usage": {"total_tokens": 42},
            },
        )
    )
    outcome = await OpenRouterExecutor().execute(
        {"id": "r1", "params": {"topics": ["x"]}}, make_agent(), tmp_path, on_event
    )
    assert outcome.status == "completed"
    assert outcome.cost_usd == 0.0  # :free model
    files = list(tmp_path.glob("test-agent-*.md"))
    assert len(files) == 1
    assert files[0].read_text() == "# Brief\n\nhello world"
    assert "tokens=42" in outcome.result
    assert ("message", {"text": "# Brief\n\nhello world"}) in collected


@respx.mock
async def test_default_model_comes_from_settings(tmp_path, events, api_key, monkeypatch):
    _, on_event = events
    monkeypatch.setattr(settings, "openrouter_default_model", "picked/by-settings:free")
    route = respx.post(OR_URL).mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    )
    await OpenRouterExecutor().execute(
        {"id": "r1", "params": {}}, make_agent(model="default"), tmp_path, on_event
    )
    import json

    assert json.loads(route.calls[0].request.content)["model"] == "picked/by-settings:free"


@respx.mock
async def test_rate_limit_fails_cleanly(tmp_path, events, api_key):
    _, on_event = events
    respx.post(OR_URL).mock(return_value=httpx.Response(429, text="rate limited"))
    outcome = await OpenRouterExecutor().execute(
        {"id": "r1", "params": {}}, make_agent(), tmp_path, on_event
    )
    assert outcome.status == "failed"
    assert "429" in outcome.error
    assert list(tmp_path.glob("*.md")) == []


@respx.mock
async def test_embedded_error_fails_cleanly(tmp_path, events, api_key):
    _, on_event = events
    respx.post(OR_URL).mock(
        return_value=httpx.Response(200, json={"error": {"message": "model overloaded"}})
    )
    outcome = await OpenRouterExecutor().execute(
        {"id": "r1", "params": {}}, make_agent(), tmp_path, on_event
    )
    assert outcome.status == "failed"
    assert "model overloaded" in outcome.error


async def test_paid_model_refused_by_default(tmp_path, events, api_key):
    _, on_event = events
    outcome = await OpenRouterExecutor().execute(
        {"id": "r1", "params": {}},
        make_agent(model="anthropic/claude-sonnet-5"),
        tmp_path,
        on_event,
    )
    assert outcome.status == "failed"
    assert "OPENROUTER_ALLOW_PAID" in outcome.error
    assert list(tmp_path.glob("*.md")) == []


@respx.mock
async def test_paid_model_allowed_when_opted_in(tmp_path, events, api_key, monkeypatch):
    _, on_event = events
    monkeypatch.setattr(settings, "openrouter_allow_paid", True)
    respx.post(OR_URL).mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    )
    outcome = await OpenRouterExecutor().execute(
        {"id": "r1", "params": {}},
        make_agent(model="anthropic/claude-sonnet-5"),
        tmp_path,
        on_event,
    )
    assert outcome.status == "completed"
    assert outcome.cost_usd is None  # paid model: cost unknown, NOT claimed to be zero


async def test_missing_key_fails_without_calling_api(tmp_path, events, monkeypatch):
    _, on_event = events
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    outcome = await OpenRouterExecutor().execute(
        {"id": "r1", "params": {}}, make_agent(), tmp_path, on_event
    )
    assert outcome.status == "failed"
    assert "OPENROUTER_API_KEY" in outcome.error
