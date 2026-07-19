"""Ollama chat provider (ChatProvider #3): local models, unlimited, private, $0.

Exposed as virtual models `octo/local-<tag>` (e.g. octo/local-qwen3.5-4b for the
Ollama tag qwen3.5:4b). Disabled unless OLLAMA_BASE_URL is configured — hosts opt in
per-.env (treco runs it; the Mac may not). Speaks Ollama's OpenAI-compatible /v1."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from octo.config import settings

log = logging.getLogger("octo.providers.ollama")

LOCAL_PREFIX = "octo/local-"

_tags_cache: tuple[float, list[str]] = (0.0, [])
TAGS_CACHE_TTL = 60.0  # short: `ollama pull` should show up quickly


class OllamaUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(settings.ollama_base_url)


def virtual_name(tag: str) -> str:
    """qwen3.5:4b -> octo/local-qwen3.5-4b"""
    return LOCAL_PREFIX + tag.replace(":", "-")


async def installed_tags() -> list[str]:
    """Ollama's installed model tags (cached ~1min); [] when unreachable/disabled."""
    global _tags_cache
    if not enabled():
        return []
    ts, cached = _tags_cache
    if cached and time.monotonic() - ts < TAGS_CACHE_TTL:
        return cached
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            r.raise_for_status()
        tags = sorted(m["name"] for m in r.json().get("models", []))
    except Exception as exc:
        log.warning("ollama unreachable at %s: %s", settings.ollama_base_url, exc)
        return []
    _tags_cache = (time.monotonic(), tags)
    return tags


async def resolve_local(requested: str) -> str:
    """octo/local-<name> -> the installed Ollama tag it refers to."""
    if not enabled():
        raise OllamaUnavailable(
            f"model '{requested}' is a local model but OLLAMA_BASE_URL is not configured "
            "on this host"
        )
    tags = await installed_tags()
    for tag in tags:
        if virtual_name(tag) == requested:
            return tag
    raise OllamaUnavailable(
        f"no installed Ollama model matches '{requested}' "
        f"(installed: {[virtual_name(t) for t in tags] or 'none'} — `ollama pull` it first)"
    )


class OllamaProvider:
    def resolve_model(self, model: str) -> str:
        return model  # resolution happens async via resolve_local() at route time

    async def complete(self, payload: dict[str, Any]) -> httpx.Response:
        async with httpx.AsyncClient(timeout=600) as client:  # CPU inference is slow
            return await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions", json=payload
            )

    @asynccontextmanager
    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[AsyncIterator[bytes]]:
        async with httpx.AsyncClient(timeout=600) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={**payload, "stream": True},
            ) as r:
                if r.status_code != 200:
                    from octo.providers.openrouter import ProviderError

                    body = (await r.aread()).decode(errors="replace")[:300]
                    raise ProviderError(r.status_code, f"ollama: {body or 'no detail'}")
                yield r.aiter_bytes()

    async def list_models(self) -> list[str]:
        return [virtual_name(t) for t in await installed_tags()]
