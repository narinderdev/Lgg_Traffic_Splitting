from __future__ import annotations

import logging
from collections.abc import Mapping
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _detect_webhook_kind(url: str, configured_kind: str) -> str:
    kind = configured_kind.strip().lower()
    if kind and kind != "auto":
        return kind

    hostname = urlparse(url).hostname or ""
    if hostname.endswith("hooks.slack.com"):
        return "slack"
    return "generic"


def _build_generic_payload(
    title: str,
    detail: str,
    severity: str,
    attributes: Mapping[str, str | int | float] | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "text": f"[{severity.upper()}] {title}\n{detail}",
        "severity": severity,
        "title": title,
        "detail": detail,
    }
    if attributes:
        payload["attributes"] = dict(attributes)
    return payload


def _build_slack_payload(
    title: str,
    detail: str,
    severity: str,
    attributes: Mapping[str, str | int | float] | None,
) -> dict[str, object]:
    severity_upper = severity.upper()
    emoji = {
        "critical": ":rotating_light:",
        "error": ":warning:",
        "warning": ":large_yellow_circle:",
        "info": ":information_source:",
    }.get(severity.lower(), ":bell:")
    fields = []
    if attributes:
        for key, value in attributes.items():
            fields.append({"type": "mrkdwn", "text": f"*{key}*\n{value}"})

    blocks: list[dict[str, object]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{emoji} *[{severity_upper}]* {title}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": detail},
        },
    ]
    if fields:
        blocks.append({"type": "section", "fields": fields[:10]})

    return {
        "text": f"[{severity_upper}] {title}",
        "blocks": blocks,
    }


def _build_alert_payload(
    webhook_url: str,
    configured_kind: str,
    title: str,
    detail: str,
    severity: str,
    attributes: Mapping[str, str | int | float] | None,
) -> dict[str, object]:
    kind = _detect_webhook_kind(webhook_url, configured_kind)
    if kind == "slack":
        return _build_slack_payload(title, detail, severity, attributes)
    return _build_generic_payload(title, detail, severity, attributes)


async def send_alert(
    title: str,
    detail: str,
    severity: str = "error",
    attributes: Mapping[str, str | int | float] | None = None,
) -> None:
    if not settings.alert_webhook_url:
        logger.warning("Alert not delivered because ALERT_WEBHOOK_URL is not configured: %s", title)
        return

    payload = _build_alert_payload(
        settings.alert_webhook_url,
        settings.alert_webhook_kind,
        title,
        detail,
        severity,
        attributes,
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.alert_webhook_url, json=payload)
            response.raise_for_status()
    except Exception:
        logger.exception("Failed to deliver alert webhook")
