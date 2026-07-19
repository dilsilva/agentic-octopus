"""Tool-loop integration: real Postgres, mocked provider + mocked tools."""

from pathlib import Path

import httpx
import pytest
import respx

from octo import chat
from octo.config import settings
from octo.registry import load_registry
from octo.tools import web as web_tools

REPO_AGENTS = Path(__file__).resolve().parents[2] / "agents"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"

TOOL_REPLY = 'TOOL_CALL {"tool": "web_search", "args": {"query": "k8s 1.34 changes"}}'
FINAL_REPLY = "Kubernetes 1.34 added X ([source](https://k8s.test/blog))."


@pytest.fixture
def registry():
    return load_registry(REPO_AGENTS)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "chat_max_tool_calls", 2)
    monkeypatch.setattr(settings, "chat_show_routed_model", False)  # tested separately
    monkeypatch.setattr(
        web_tools,
        "_search_sync",
        lambda q, n: [{"title": "K8s blog", "url": "https://k8s.test/blog", "snippet": "1.34"}],
    )


def completion(text):
    return httpx.Response(
        200,
        json={
            "model": "some/model:free",
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        },
    )


@respx.mock
async def test_send_runs_tool_loop_and_persists_audit(pool, registry):
    respx.post(OR_URL).mock(side_effect=[completion(TOOL_REPLY), completion(FINAL_REPLY)])
    convo = await chat.create_conversation(pool)
    reply = await chat.send(pool, registry, str(convo["id"]), "what changed in k8s 1.34?")

    assert reply["content"] == FINAL_REPLY
    msgs = await chat.get_messages(pool, str(convo["id"]))
    assert [m["role"] for m in msgs] == ["user", "tool", "assistant"]
    tool_row = msgs[1]
    assert tool_row["metadata"]["call"]["tool"] == "web_search"
    assert tool_row["metadata"]["result"]["results"][0]["url"] == "https://k8s.test/blog"


@respx.mock
async def test_tool_results_reach_the_model(pool, registry):
    import json as _json

    route = respx.post(OR_URL).mock(side_effect=[completion(TOOL_REPLY), completion(FINAL_REPLY)])
    convo = await chat.create_conversation(pool)
    await chat.send(pool, registry, str(convo["id"]), "news?")
    second_call = _json.loads(route.calls[1].request.content)
    joined = _json.dumps(second_call["messages"])
    assert "k8s.test/blog" in joined  # search results injected into round 2
    assert second_call["messages"][0]["role"] == "system"
    assert "TOOL_CALL" in second_call["messages"][0]["content"]  # protocol prompt present


@respx.mock
async def test_tool_budget_is_bounded(pool, registry):
    # model asks for tools forever; loop must stop at chat_max_tool_calls
    route = respx.post(OR_URL).mock(return_value=completion(TOOL_REPLY))
    convo = await chat.create_conversation(pool)
    await chat.send(pool, registry, str(convo["id"]), "loop forever please")
    assert route.call_count == settings.chat_max_tool_calls + 1
    msgs = await chat.get_messages(pool, str(convo["id"]))
    assert [m["role"] for m in msgs].count("tool") == settings.chat_max_tool_calls


@respx.mock
async def test_persona_without_tools_never_loops(pool, registry, tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    (d / "agent.yaml").write_text("name: plain\n")
    (d / "prompt.md").write_text("no tools here")
    plain_registry = load_registry(tmp_path)
    route = respx.post(OR_URL).mock(return_value=completion(TOOL_REPLY))
    convo = await chat.create_conversation(pool, persona="plain")
    reply = await chat.send(pool, plain_registry, str(convo["id"]), "hi")
    assert route.call_count == 1  # marker treated as plain text, no loop
    assert reply["content"] == TOOL_REPLY


def sse_response(text):
    import json as _json

    chunks = []
    for i in range(0, len(text), 7):
        event = {
            "model": "some/model:free",
            "choices": [{"delta": {"content": text[i : i + 7]}}],
        }
        chunks.append(f"data: {_json.dumps(event)}\n\n".encode())
    return httpx.Response(
        200,
        content=b"".join(chunks) + b"data: [DONE]\n\n",
        headers={"content-type": "text/event-stream"},
    )


@respx.mock
async def test_tags_persisted_on_assistant_message(pool, registry):
    respx.post(OR_URL).mock(return_value=completion("hi"))
    convo = await chat.create_conversation(pool)
    reply = await chat.send(
        pool, registry, str(convo["id"]), "hello", tags={"topic": "infra", "surface": "cli"}
    )
    tags = reply["tags"]
    assert tags["topic"] == "infra"  # manual category
    assert tags["surface"] == "cli"  # manual overrides auto
    assert tags["persona"] == "chat-assistant"  # auto-derived
    assert tags["provider"] == "openrouter"


@respx.mock
async def test_routed_model_prefix_on_auto(pool, registry, monkeypatch):
    monkeypatch.setattr(settings, "chat_show_routed_model", True)
    monkeypatch.setattr(settings, "openrouter_default_model", "octo/auto")
    respx.post(OR_URL).mock(return_value=completion("plain answer"))
    convo = await chat.create_conversation(pool)  # model 'default' -> octo/auto
    reply = await chat.send(pool, registry, str(convo["id"]), "hello")
    assert reply["content"].startswith("`[some/model:free]`\n\n")
    assert reply["model"] == "some/model:free"


@respx.mock
async def test_no_prefix_for_explicit_model(pool, registry, monkeypatch):
    monkeypatch.setattr(settings, "chat_show_routed_model", True)
    respx.post(OR_URL).mock(return_value=completion("plain answer"))
    convo = await chat.create_conversation(pool, model="some/model:free")
    reply = await chat.send(pool, registry, str(convo["id"]), "hello")
    assert reply["content"] == "plain answer"


@respx.mock
async def test_stream_hides_tool_round_and_streams_final(pool, registry):
    respx.post(OR_URL).mock(side_effect=[sse_response(TOOL_REPLY), sse_response(FINAL_REPLY)])
    convo = await chat.create_conversation(pool)
    events = [ev async for ev in chat.send_stream(pool, registry, str(convo["id"]), "k8s news?")]
    tool_events = [e for e in events if "tool_status" in e]
    deltas = "".join(
        c["choices"][0]["delta"]["content"]
        for c in events
        if c.get("object") == "chat.completion.chunk"
    )
    assert len(tool_events) == 1
    assert tool_events[0]["tool_status"]["tool"] == "web_search"
    assert deltas == FINAL_REPLY  # the TOOL_CALL text never reached the client
    assert events[-1].get("done") is True
    msgs = await chat.get_messages(pool, str(convo["id"]))
    assert [m["role"] for m in msgs] == ["user", "tool", "assistant"]
    assert msgs[-1]["content"] == FINAL_REPLY
