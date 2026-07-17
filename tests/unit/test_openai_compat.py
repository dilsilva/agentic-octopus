import httpx
import pytest
import respx

from octo.config import settings
from octo.providers import openrouter as orp

AUTH = {"Authorization": f"Bearer {settings.octo_api_token}"}
OR_URL = "https://openrouter.ai/api/v1/chat/completions"


@pytest.fixture(autouse=True)
def fresh_models_cache(monkeypatch):
    monkeypatch.setattr(orp, "_models_cache", (0.0, []))
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")


@respx.mock
def test_models_lists_only_free(client_without_db):
    respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "a/b:free"}, {"id": "paid/model"}]})
    )
    r = client_without_db.get("/v1/models", headers=AUTH)
    assert r.status_code == 200
    assert [m["id"] for m in r.json()["data"]] == ["a/b:free"]


@respx.mock
def test_completions_passthrough(client_without_db):
    upstream = {"choices": [{"message": {"content": "hi"}}], "usage": {"total_tokens": 5}}
    respx.post(OR_URL).mock(return_value=httpx.Response(200, json=upstream))
    r = client_without_db.post(
        "/v1/chat/completions",
        json={"model": "a/b:free", "messages": [{"role": "user", "content": "hey"}]},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json() == upstream


@respx.mock
def test_paid_model_rejected_without_upstream_call(client_without_db):
    route = respx.post(OR_URL)
    r = client_without_db.post(
        "/v1/chat/completions",
        json={"model": "anthropic/claude-sonnet-5", "messages": []},
        headers=AUTH,
    )
    assert r.status_code == 400
    assert "OPENROUTER_ALLOW_PAID" in r.json()["error"]["message"]
    assert route.call_count == 0


@respx.mock
def test_quota_maps_to_readable_429(client_without_db):
    respx.post(OR_URL).mock(return_value=httpx.Response(429))
    r = client_without_db.post(
        "/v1/chat/completions", json={"model": "a/b:free", "messages": []}, headers=AUTH
    )
    assert r.status_code == 429
    assert "free-tier quota" in r.json()["error"]["message"]


@respx.mock
def test_streaming_passthrough_verbatim(client_without_db):
    sse_body = (
        b'data: {"choices":[{"delta":{"content":"he"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"y"}}],"usage":{"total_tokens":7}}\n\n'
        b"data: [DONE]\n\n"
    )
    respx.post(OR_URL).mock(
        return_value=httpx.Response(
            200, content=sse_body, headers={"content-type": "text/event-stream"}
        )
    )
    r = client_without_db.post(
        "/v1/chat/completions",
        json={"model": "a/b:free", "messages": [], "stream": True},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert b'"content":"he"' in r.content
    assert b"[DONE]" in r.content


def test_auth_required(client_without_db):
    assert client_without_db.get("/v1/models").status_code == 401


def test_chat_token_scoping(client_without_db, monkeypatch):
    monkeypatch.setattr(settings, "octo_chat_token", "chat-secret")
    chat_auth = {"Authorization": "Bearer chat-secret"}
    # chat scope: allowed on /chat and /v1 (never 401)
    assert client_without_db.get("/chat/conversations", headers=chat_auth).status_code != 401
    # admin surfaces: refused
    assert client_without_db.get("/runs", headers=chat_auth).status_code == 401
    assert client_without_db.get("/agents", headers=chat_auth).status_code == 401
    # admin token still valid everywhere
    assert client_without_db.get("/agents", headers=AUTH).status_code == 200
