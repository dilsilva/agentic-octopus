"""ChatProvider protocol — the provider seam for conversational completions.

Mirrors the AgentExecutor pattern (ADR-0002): structural typing, one factory.
Billing policy (e.g. OpenRouter's :free guard) is NOT part of the protocol —
it's applied by callers for providers where cost exists.
"""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

import httpx


class ChatProvider(Protocol):
    def resolve_model(self, model: str) -> str:
        """Map 'default' to the provider's configured default model id."""
        ...

    async def complete(self, payload: dict[str, Any]) -> httpx.Response:
        """Non-streaming chat completion. payload is OpenAI chat-completions shaped."""
        ...

    def stream(self, payload: dict[str, Any]) -> AbstractAsyncContextManager[AsyncIterator[bytes]]:
        """Streaming chat completion: async context manager yielding raw SSE byte chunks."""
        ...

    async def list_models(self) -> list[str]:
        """Model ids this provider offers under current policy."""
        ...


def get_chat_provider(name: str) -> ChatProvider:
    if name == "openrouter":
        from octo.providers.openrouter import OpenRouterProvider

        return OpenRouterProvider()
    raise ValueError(f"no chat provider registered for '{name}'")
