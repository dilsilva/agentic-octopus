"""Bearer-token auth. Two scopes:

- OCTO_API_TOKEN — admin: valid everywhere (runs, approvals, schedules, chat).
- OCTO_CHAT_TOKEN — optional client scope: valid ONLY on chat surfaces (/chat/*, /v1/*).
  This is the token handed to chat UIs (Open WebUI); a credential stored inside a
  third-party container can chat but cannot approve runs or drive agents.

Swapped for IAM at the GCP phase (RFC-0001 P4)."""

from fastapi import Header, HTTPException

from octo.config import settings


async def require_token(authorization: str | None = Header(default=None)) -> None:
    """Admin scope."""
    if authorization != f"Bearer {settings.octo_api_token}":
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


async def require_chat_token(authorization: str | None = Header(default=None)) -> None:
    """Chat scope: admin token OR the client-scoped chat token (when configured)."""
    valid = {f"Bearer {settings.octo_api_token}"}
    if settings.octo_chat_token:
        valid.add(f"Bearer {settings.octo_chat_token}")
    if authorization not in valid:
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")
