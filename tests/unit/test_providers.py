import httpx
import pytest
import respx

from octo.config import settings
from octo.providers import openrouter as orp
from octo.providers.base import get_chat_provider
from octo.providers.openrouter import (
    OpenRouterProvider,
    PaidModelRefused,
    QuotaExceeded,
    enforce_free,
    resolve_model,
)


def test_resolve_model_default(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_default_model", "x/y:free")
    assert resolve_model("default") == "x/y:free"
    assert resolve_model("a/b:free") == "a/b:free"


def test_enforce_free_blocks_paid(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_allow_paid", False)
    enforce_free("a/b:free")  # no raise
    with pytest.raises(PaidModelRefused):
        enforce_free("anthropic/claude-sonnet-5")


def test_enforce_free_opt_in(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_allow_paid", True)
    enforce_free("anthropic/claude-sonnet-5")  # no raise


def test_factory():
    assert isinstance(get_chat_provider("openrouter"), OpenRouterProvider)
    with pytest.raises(ValueError):
        get_chat_provider("nope")


@respx.mock
async def test_complete_maps_429_to_quota(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "k")
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(429, text="slow down")
    )
    with pytest.raises(QuotaExceeded, match="429"):
        await OpenRouterProvider().complete({"model": "a/b:free", "messages": []})


@respx.mock
async def test_list_models_filters_free_and_caches(monkeypatch):
    monkeypatch.setattr(orp, "_models_cache", (0.0, []))
    route = respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "a/b:free"}, {"id": "c/d"}, {"id": "e/f:free"}]},
        )
    )
    p = OpenRouterProvider()
    assert await p.list_models() == ["a/b:free", "e/f:free"]
    assert await p.list_models() == ["a/b:free", "e/f:free"]  # cached
    assert route.call_count == 1


@pytest.fixture
def router_setup(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "k")
    monkeypatch.setattr(
        settings, "openrouter_preferred_models", "one/a:free,two/b:free,three/c:free"
    )


def test_auto_model_passes_cost_guard(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_allow_paid", False)
    enforce_free(orp.AUTO_MODEL)  # virtual model expands to :free only — no raise


def test_router_candidates_never_include_billable(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_preferred_models", "one/a:free,paid/model,two/b:free")
    assert orp.router_candidates() == ["one/a:free", "two/b:free"]


def test_router_candidates_capped_at_openrouter_limit(monkeypatch):
    monkeypatch.setattr(
        settings,
        "openrouter_preferred_models",
        "one/a:free,two/b:free,three/c:free,four/d:free,five/e:free",
    )
    assert orp.router_candidates() == ["one/a:free", "two/b:free", "three/c:free"]


def test_route_payload_expands_auto_to_native_fallback_array(router_setup):
    routed = orp.route_payload({"model": orp.AUTO_MODEL, "messages": [1]})
    assert "model" not in routed
    assert routed["models"] == ["one/a:free", "two/b:free", "three/c:free"]
    # explicit models pass through untouched
    explicit = orp.route_payload({"model": "one/a:free", "messages": [1]})
    assert explicit == {"model": "one/a:free", "messages": [1]}


@respx.mock
async def test_auto_complete_sends_models_array(router_setup):
    import json as _json

    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"model": "two/b:free", "choices": [{"message": {"content": "ok"}}]}
        )
    )
    r = await OpenRouterProvider().complete({"model": orp.AUTO_MODEL, "messages": []})
    assert r.status_code == 200
    sent = _json.loads(route.calls[0].request.content)
    assert "model" not in sent
    assert sent["models"] == ["one/a:free", "two/b:free", "three/c:free"]
    assert route.call_count == 1  # ONE request — server-side fallback, no quota burn


@respx.mock
async def test_auto_stream_sends_models_array(router_setup):
    import json as _json

    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n',
            headers={"content-type": "text/event-stream"},
        )
    )
    received = b""
    async with OpenRouterProvider().stream({"model": orp.AUTO_MODEL, "messages": []}) as chunks:
        async for c in chunks:
            received += c
    assert b'"content":"ok"' in received
    sent = _json.loads(route.calls[0].request.content)
    assert sent["models"] == ["one/a:free", "two/b:free", "three/c:free"]


@respx.mock
async def test_list_models_fallback_on_failure(monkeypatch):
    monkeypatch.setattr(orp, "_models_cache", (0.0, []))
    monkeypatch.setattr(settings, "openrouter_default_model", "fallback/model:free")
    respx.get("https://openrouter.ai/api/v1/models").mock(return_value=httpx.Response(500))
    assert await OpenRouterProvider().list_models() == ["fallback/model:free"]
