from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.conversion import Conversion
from app.models.experiment import Experiment
from app.models.impression import Impression
from app.schemas.common import MonitoringAlert, MonitoringSummary, MonitoringThresholds
from app.services.metrics import CLOUDFLARE_SYNC_COUNT, INGEST_REJECTED_COUNT, get_counter_value

settings = get_settings()


async def get_monitoring_summary(session: AsyncSession) -> MonitoringSummary:
    now = datetime.now(UTC)
    lookback = timedelta(minutes=settings.alert_lookback_minutes)
    recent_start = now - lookback
    previous_start = recent_start - lookback

    recent_impressions = await session.scalar(
        select(func.count(Impression.id)).where(Impression.ts >= recent_start, Impression.ts < now)
    )
    previous_impressions = await session.scalar(
        select(func.count(Impression.id)).where(Impression.ts >= previous_start, Impression.ts < recent_start)
    )
    recent_conversions = await session.scalar(
        select(func.count(Conversion.id)).where(Conversion.ts >= recent_start, Conversion.ts < now)
    )
    active_experiments = await session.scalar(
        select(func.count(Experiment.id)).where(Experiment.status == "active")
    )
    paused_experiments = await session.scalar(
        select(func.count(Experiment.id)).where(Experiment.status == "paused")
    )

    ingest_rejections = (
        get_counter_value(INGEST_REJECTED_COUNT, kind="impression")
        + get_counter_value(INGEST_REJECTED_COUNT, kind="conversion")
    )
    cloudflare_sync_failures = (
        get_counter_value(CLOUDFLARE_SYNC_COUNT, operation="upsert", status="failure")
        + get_counter_value(CLOUDFLARE_SYNC_COUNT, operation="delete", status="failure")
    )
    traffic_ratio = None
    if (previous_impressions or 0) > 0:
        traffic_ratio = round((recent_impressions or 0) / (previous_impressions or 1), 4)
    recent_conversion_rate = None
    if (recent_impressions or 0) > 0:
        recent_conversion_rate = round((recent_conversions or 0) / (recent_impressions or 1), 4)

    alerts: list[MonitoringAlert] = []

    if settings.alert_min_recent_impressions > 0 and (recent_impressions or 0) < settings.alert_min_recent_impressions:
        alerts.append(
            MonitoringAlert(
                code="low_recent_impressions",
                severity="warning",
                message="Recent impressions are below the configured threshold.",
                current_value=int(recent_impressions or 0),
                threshold=settings.alert_min_recent_impressions,
            )
        )

    if traffic_ratio is not None:
        if traffic_ratio < settings.alert_min_traffic_ratio:
            alerts.append(
                MonitoringAlert(
                    code="traffic_drop",
                    severity="critical",
                    message="Recent traffic dropped compared with the previous lookback window.",
                    current_value=traffic_ratio,
                    threshold=settings.alert_min_traffic_ratio,
                )
            )

    if ingest_rejections > settings.alert_max_ingest_rejections:
        alerts.append(
            MonitoringAlert(
                code="ingest_rejections",
                severity="warning",
                message="Rejected ingest events exceed the configured threshold.",
                current_value=ingest_rejections,
                threshold=settings.alert_max_ingest_rejections,
            )
        )

    if cloudflare_sync_failures > settings.alert_max_cloudflare_sync_failures:
        alerts.append(
            MonitoringAlert(
                code="cloudflare_sync_failures",
                severity="critical",
                message="Cloudflare KV sync failures exceed the configured threshold.",
                current_value=cloudflare_sync_failures,
                threshold=settings.alert_max_cloudflare_sync_failures,
            )
        )

    return MonitoringSummary(
        generated_at=now,
        lookback_minutes=settings.alert_lookback_minutes,
        recent_impressions=int(recent_impressions or 0),
        previous_impressions=int(previous_impressions or 0),
        recent_conversions=int(recent_conversions or 0),
        traffic_ratio=traffic_ratio,
        recent_conversion_rate=recent_conversion_rate,
        active_experiments=int(active_experiments or 0),
        paused_experiments=int(paused_experiments or 0),
        ingest_rejections=int(ingest_rejections),
        cloudflare_sync_failures=int(cloudflare_sync_failures),
        thresholds=MonitoringThresholds(
            lookback_minutes=settings.alert_lookback_minutes,
            min_recent_impressions=settings.alert_min_recent_impressions,
            min_traffic_ratio=settings.alert_min_traffic_ratio,
            max_ingest_rejections=settings.alert_max_ingest_rejections,
            max_cloudflare_sync_failures=settings.alert_max_cloudflare_sync_failures,
        ),
        alerts=alerts,
    )
