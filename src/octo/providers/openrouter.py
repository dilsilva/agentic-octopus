"""OpenRouter chat provider + the :free cost-guard policy (shared by the chat
service, the /v1 shim, and OpenRouterExecutor).

Includes the smart router: the virtual model 'octo/auto' expands to the preferred
:free candidates, skipping ones in cooldown after 404/429/5xx failures."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from octo.config import settings

log = logging.getLogger("octo.providers.openrouter")


class PaidModelRefused(Exception):
    pass


class ProviderError(Exception):
    """Upstream provider rejected the request (e.g. model has no live endpoint)."""

    def __init__(self, status: int, detail: str):
        self.status = status
        super().__init__(f"openrouter {status}: {detail}")


class QuotaExceeded(Exception):
    """OpenRouter free-tier quota hit (50/day without credits, 20/min)."""

    MESSAGE = (
        "OpenRouter free-tier quota exceeded (HTTP 429: 50 requests/day without credits, "
        "20/minute) — daily quota resets at midnight UTC"
    )


AUTO_MODEL = "octo/auto"

# OpenRouter rejects `models` fallback arrays longer than 3 with a 400.
MAX_FALLBACK_MODELS = 3


def resolve_model(model: str) -> str:
    return settings.openrouter_default_model if model == "default" else model


def router_candidates() -> list[str]:
    """Preferred :free models, best-first, capped at MAX_FALLBACK_MODELS. Fed to
    OpenRouter's native `models` fallback array — failover happens server-side
    within ONE request (no extra daily-quota burn per attempt)."""
    free = [
        m.strip()
        for m in settings.openrouter_preferred_models.split(",")
        if m.strip().endswith(":free")  # the router NEVER routes to a billable model
    ]
    return free[:MAX_FALLBACK_MODELS]


def route_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Expand the virtual octo/auto model into OpenRouter's fallback array."""
    if payload.get("model") != AUTO_MODEL:
        return payload
    routed = {k: v for k, v in payload.items() if k != "model"}
    routed["models"] = router_candidates()
    return routed


def enforce_free(model: str) -> None:
    """Cost guard: only :free models unless the operator explicitly opted into paid.
    The virtual router model passes — it expands exclusively to :free candidates."""
    if model == AUTO_MODEL:
        return
    if not model.endswith(":free") and not settings.openrouter_allow_paid:
        raise PaidModelRefused(
            f"model '{model}' is not a :free variant and OPENROUTER_ALLOW_PAID is off "
            "— refusing to run a potentially billable request"
        )


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.openrouter_api_key}"}


_models_cache: tuple[float, list[str]] = (0.0, [])
MODELS_CACHE_TTL = 3600.0


class OpenRouterProvider:
    def resolve_model(self, model: str) -> str:
        return resolve_model(model)

    async def complete(self, payload: dict[str, Any]) -> httpx.Response:
        payload = route_payload(payload)
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=_headers(),
                json=payload,
            )
        if r.status_code == 429:
            raise QuotaExceeded(QuotaExceeded.MESSAGE)
        return r

    @asynccontextmanager
    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[AsyncIterator[bytes]]:
        payload = route_payload(payload)
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{settings.openrouter_base_url}/chat/completions",
                headers=_headers(),
                json={**payload, "stream": True},
            ) as r:
                if r.status_code == 429:
                    raise QuotaExceeded(QuotaExceeded.MESSAGE)
                if r.status_code != 200:
                    body = (await r.aread()).decode(errors="replace")[:300]
                    raise ProviderError(r.status_code, body or "no detail")
                yield r.aiter_bytes()

    async def list_models(self) -> list[str]:
        """All :free model ids, cached ~1h; falls back to the configured default."""
        global _models_cache
        ts, cached = _models_cache
        if cached and time.monotonic() - ts < MODELS_CACHE_TTL:
            return cached
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(f"{settings.openrouter_base_url}/models")
                r.raise_for_status()
            models = sorted(m["id"] for m in r.json()["data"] if m["id"].endswith(":free"))
        except Exception:
            models = []
        if not models:
            models = [settings.openrouter_default_model]
        _models_cache = (time.monotonic(), models)
        return models
