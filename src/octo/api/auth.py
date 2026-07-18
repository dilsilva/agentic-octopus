"""Bearer-token auth. Two scopes:

- OCTO_API_TOKEN — admin: valid everywhere (runs, approvals, schedules, chat).
- OCTO_CHAT_TOKEN — optional client scope: valid ONLY on chat surfaces (/chat/*, /v1/*).
  This is the token handed to chat UIs (Open WebUI); a credential stored inside a
  third-party container can chat but cannot approve runs or drive agents.

Uses HTTPBearer so the OpenAPI schema carries the security scheme (the Authorize
button in /docs works). Swapped for IAM at the GCP phase (RFC-0001 P4)."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from octo.config import settings

_bearer = HTTPBearer(auto_error=False, description="OCTO_API_TOKEN (admin) — see .env")
_chat_bearer = HTTPBearer(
    auto_error=False, description="OCTO_CHAT_TOKEN (chat scope) or OCTO_API_TOKEN (admin)"
)


async def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Admin scope."""
    if credentials is None or credentials.credentials != settings.octo_api_token:
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


async def require_chat_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_chat_bearer),
) -> None:
    """Chat scope: admin token OR the client-scoped chat token (when configured)."""
    valid = {settings.octo_api_token}
    if settings.octo_chat_token:
        valid.add(settings.octo_chat_token)
    if credentials is None or credentials.credentials not in valid:
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")
