import httpx
import respx

from octo.chat import parse_tool_call, tool_protocol_prompt
from octo.tools import run_tool
from octo.tools import web as web_tools


async def test_run_tool_unknown():
    result = await run_tool("teleport", {})
    assert "unknown tool" in result["error"]


async def test_web_search_happy(monkeypatch):
    monkeypatch.setattr(
        web_tools,
        "_search_sync",
        lambda q, n: [{"title": "T", "url": "https://x.test", "snippet": "s"}],
    )
    result = await run_tool("web_search", {"query": "anything"})
    assert result["results"][0]["url"] == "https://x.test"


async def test_web_search_failure_is_data_not_exception(monkeypatch):
    def boom(q, n):
        raise RuntimeError("ddg down")

    monkeypatch.setattr(web_tools, "_search_sync", boom)
    result = await run_tool("web_search", {"query": "x"})
    assert "search failed" in result["error"]


async def test_web_search_requires_query():
    assert "requires" in (await run_tool("web_search", {}))["error"]


@respx.mock
async def test_fetch_page_extracts_text():
    respx.get("https://site.test/a").mock(
        return_value=httpx.Response(
            200, text="<html><script>x()</script><body><p>Hello <b>world</b></p></body></html>"
        )
    )
    result = await run_tool("fetch_page", {"url": "https://site.test/a"})
    assert result["text"] == "Hello world"
    assert result["truncated"] is False


@respx.mock
async def test_fetch_page_http_error_is_data():
    respx.get("https://site.test/gone").mock(return_value=httpx.Response(404))
    result = await run_tool("fetch_page", {"url": "https://site.test/gone"})
    assert "HTTP 404" in result["error"]


async def test_fetch_page_rejects_non_http():
    assert "requires" in (await run_tool("fetch_page", {"url": "file:///etc/passwd"}))["error"]


def test_parse_tool_call_variants():
    assert parse_tool_call('TOOL_CALL {"tool": "web_search", "args": {"query": "k8s"}}') == (
        "web_search",
        {"query": "k8s"},
    )
    # marker not on first line still parses (lenient)
    assert parse_tool_call('thinking...\nTOOL_CALL {"tool": "fetch_page", "args": {}}') == (
        "fetch_page",
        {},
    )
    assert parse_tool_call("just a normal answer") is None
    assert parse_tool_call("TOOL_CALL not-json") is None
    assert parse_tool_call('TOOL_CALL {"no_tool_key": 1}') is None


def test_tool_protocol_prompt_lists_tools():
    p = tool_protocol_prompt(["web_search", "fetch_page"])
    assert "TOOL_CALL" in p
    assert "web_search" in p and "fetch_page" in p
    assert "cite source urls" in p.lower()
