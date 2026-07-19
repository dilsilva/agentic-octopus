"""Web tools: free/keyless search (DuckDuckGo via ddgs) + page fetch.

Both run in a thread (the libs are sync) and always RETURN a result dict —
tool failures are data the model can react to, never exceptions that kill a chat.
"""

import asyncio
import logging
from typing import Any

import httpx

log = logging.getLogger("octo.tools.web")

SEARCH_MAX_RESULTS = 6
FETCH_MAX_CHARS = 6000
FETCH_TIMEOUT = 20


def _search_sync(query: str, max_results: int) -> list[dict[str, str]]:
    from ddgs import DDGS

    with DDGS() as ddgs:
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:300],
            }
            for r in ddgs.text(query, max_results=max_results)
        ]


async def web_search(args: dict[str, Any]) -> dict[str, Any]:
    """{"query": str, "max_results"?: int} -> {"results": [{title,url,snippet}]}"""
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "web_search requires a 'query'"}
    limit = min(int(args.get("max_results", SEARCH_MAX_RESULTS)), 10)
    try:
        results = await asyncio.to_thread(_search_sync, query, limit)
    except Exception as exc:
        log.warning("web_search failed for %r: %s", query, exc)
        return {"error": f"search failed: {exc}"}
    if not results:
        return {"results": [], "note": "no results — try different keywords"}
    return {"results": results}


def _extract_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text


async def fetch_page(args: dict[str, Any]) -> dict[str, Any]:
    """{"url": str} -> {"url", "text"} (readable text, truncated)"""
    url = str(args.get("url", "")).strip()
    if not url.startswith(("http://", "https://")):
        return {"error": "fetch_page requires an http(s) 'url'"}
    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT, follow_redirects=True, headers={"User-Agent": "octo-spine/0.4"}
        ) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return {"error": f"fetch failed: HTTP {r.status_code}", "url": url}
        text = await asyncio.to_thread(_extract_text, r.text)
        truncated = len(text) > FETCH_MAX_CHARS
        return {"url": url, "text": text[:FETCH_MAX_CHARS], "truncated": truncated}
    except Exception as exc:
        log.warning("fetch_page failed for %r: %s", url, exc)
        return {"error": f"fetch failed: {exc}", "url": url}


TOOL_REGISTRY = {
    "web_search": {
        "fn": web_search,
        "description": 'search the web: {"query": "...", "max_results": 5}',
    },
    "fetch_page": {
        "fn": fetch_page,
        "description": 'read a web page: {"url": "https://..."}',
    },
}


async def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return {"error": f"unknown tool '{name}' (available: {sorted(TOOL_REGISTRY)})"}
    return await tool["fn"](args)
