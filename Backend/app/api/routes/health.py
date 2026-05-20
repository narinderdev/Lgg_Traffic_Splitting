from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.services.cache import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck(response: Response) -> dict[str, object]:
    settings = get_settings()
    db_ok = False
    redis_ok = settings.redis_url is None

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_client = get_redis()
    if redis_client is not None:
        try:
            redis_ok = bool(await redis_client.ping())
        except Exception:
            redis_ok = False

    overall_ok = db_ok and redis_ok
    response.status_code = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if overall_ok else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {
            "database": "ok" if db_ok else "down",
            "redis": "ok" if redis_ok else "down",
            "cloudflare_sync": "configured" if settings.cloudflare_sync_enabled else "disabled",
        },
    }
