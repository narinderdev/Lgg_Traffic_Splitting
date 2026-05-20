from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.core.config import get_settings
from app.core.security import require_admin_api_key
from app.schemas.common import MonitoringSummary
from app.services.alerts import send_alert
from app.services.monitoring import get_monitoring_summary

settings = get_settings()

router = APIRouter(
    prefix="/monitoring",
    tags=["monitoring"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.get("/summary", response_model=MonitoringSummary)
async def monitoring_summary_endpoint(
    session: AsyncSession = Depends(db_session),
) -> MonitoringSummary:
    return await get_monitoring_summary(session)


@router.post("/alerts/dispatch", response_model=MonitoringSummary)
async def dispatch_monitoring_alerts_endpoint(
    session: AsyncSession = Depends(db_session),
) -> MonitoringSummary:
    summary = await get_monitoring_summary(session)
    for alert in summary.alerts:
        await send_alert(
            alert.code,
            alert.message,
            severity=alert.severity,
            attributes={
                "current_value": alert.current_value if alert.current_value is not None else "n/a",
                "threshold": alert.threshold if alert.threshold is not None else "n/a",
                "environment": settings.app_env,
                "lookback_minutes": summary.lookback_minutes,
                "recent_impressions": summary.recent_impressions,
                "recent_conversions": summary.recent_conversions,
            },
        )
    return summary
