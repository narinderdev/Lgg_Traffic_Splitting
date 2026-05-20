from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def send_alert(title: str, detail: str, severity: str = "error") -> None:
    if not settings.alert_webhook_url:
        logger.warning("Alert not delivered because ALERT_WEBHOOK_URL is not configured: %s", title)
        return

    payload = {
        "text": f"[{severity.upper()}] {title}\n{detail}",
        "severity": severity,
        "title": title,
        "detail": detail,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.alert_webhook_url, json=payload)
            response.raise_for_status()
    except Exception:
        logger.exception("Failed to deliver alert webhook")
