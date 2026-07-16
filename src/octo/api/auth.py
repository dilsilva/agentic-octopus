"""Static bearer-token auth — sufficient for a solo local API; swapped for IAM at the
GCP phase (RFC-0001 P4)."""

from fastapi import Header, HTTPException

from octo.config import settings


async def require_token(authorization: str | None = Header(default=None)) -> None:
    if authorization != f"Bearer {settings.octo_api_token}":
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")
