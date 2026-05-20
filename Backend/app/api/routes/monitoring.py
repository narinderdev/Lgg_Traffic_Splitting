from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.core.security import require_admin_api_key
from app.schemas.common import MonitoringSummary
from app.services.alerts import send_alert
from app.services.monitoring import get_monitoring_summary

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
        await send_alert(alert.code, alert.message, severity=alert.severity)
    return summary
