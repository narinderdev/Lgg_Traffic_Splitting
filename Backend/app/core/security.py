from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


def _validate_token(
    credentials: HTTPAuthorizationCredentials | None,
    expected: str,
    message: str,
) -> None:
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


async def require_admin_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    _validate_token(credentials, settings.admin_api_key, "Invalid admin API key")


async def require_ingest_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    _validate_token(credentials, settings.ingest_api_key, "Invalid ingest API key")
