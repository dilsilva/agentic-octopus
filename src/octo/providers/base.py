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


def route_chat_model(requested: str) -> tuple[ChatProvider, str]:
    """Per-model provider routing + billing policy, in one seam.

    'octo/claude' (or an explicit claude-* id) → Anthropic, gated on
    ANTHROPIC_API_KEY being set — selecting it is the paid opt-in. Everything
    else → the configured chat provider under the OpenRouter :free cost guard.
    """
    from octo.config import settings
    from octo.providers.claude import CLAUDE_MODEL, AnthropicChatProvider
    from octo.providers.openrouter import PaidModelRefused, enforce_free

    if requested == CLAUDE_MODEL or requested.startswith("claude-"):
        if not settings.anthropic_key_set:
            raise PaidModelRefused(
                f"model '{requested}' routes to the Anthropic API (billable) but "
                "ANTHROPIC_API_KEY is not set — add the key to opt in"
            )
        provider: ChatProvider = AnthropicChatProvider()
        return provider, provider.resolve_model(requested)

    provider = get_chat_provider(settings.chat_provider)
    model = provider.resolve_model(requested)
    enforce_free(model)
    return provider, model
