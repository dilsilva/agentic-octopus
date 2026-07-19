import httpx
import pytest
import respx

from octo.config import settings
from octo.providers import ollama as olp
from octo.providers.base import route_chat_model
from octo.providers.ollama import OllamaProvider, OllamaUnavailable, resolve_local, virtual_name

OLLAMA = "http://ollama-test:11434"


@pytest.fixture
def ollama_on(monkeypatch):
    monkeypatch.setattr(settings, "ollama_base_url", OLLAMA)
    monkeypatch.setattr(olp, "_tags_cache", (0.0, []))


def test_virtual_name_mapping():
    assert virtual_name("qwen3.5:4b") == "octo/local-qwen3.5-4b"
    assert virtual_name("qwen3:8b") == "octo/local-qwen3-8b"


async def test_disabled_host_raises_clear_error(monkeypatch):
    monkeypatch.setattr(settings, "ollama_base_url", "")
    with pytest.raises(OllamaUnavailable, match="local LLMs are disabled on this host"):
        await resolve_local("octo/local-qwen3.5-4b")


@respx.mock
async def test_resolve_local_matches_installed(ollama_on):
    respx.get(f"{OLLAMA}/api/tags").mock(
        return_value=httpx.Response(
            200, json={"models": [{"name": "qwen3.5:4b"}, {"name": "qwen3:8b"}]}
        )
    )
    assert await resolve_local("octo/local-qwen3.5-4b") == "qwen3.5:4b"
    with pytest.raises(OllamaUnavailable, match="no installed Ollama model"):
        await resolve_local("octo/local-nonexistent")


@respx.mock
async def test_route_chat_model_local_branch(ollama_on):
    respx.get(f"{OLLAMA}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}]})
    )
    provider, model, name = await route_chat_model("octo/local-qwen3.5-4b")
    assert isinstance(provider, OllamaProvider)
    assert model == "qwen3.5:4b"
    assert name == "ollama"


@respx.mock
async def test_list_models_prefixed_and_unreachable_is_empty(ollama_on):
    respx.get(f"{OLLAMA}/api/tags").mock(side_effect=httpx.ConnectError("down"))
    assert await OllamaProvider().list_models() == []


@respx.mock
async def test_complete_hits_openai_endpoint(ollama_on):
    route = respx.post(f"{OLLAMA}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"model": "qwen3.5:4b", "choices": [{"message": {"content": "oi"}}]}
        )
    )
    r = await OllamaProvider().complete({"model": "qwen3.5:4b", "messages": []})
    assert r.status_code == 200
    assert route.call_count == 1
