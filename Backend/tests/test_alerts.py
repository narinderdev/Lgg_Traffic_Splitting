from __future__ import annotations

from app.services.alerts import _build_alert_payload


def test_build_alert_payload_uses_slack_blocks_for_slack_webhooks() -> None:
    payload = _build_alert_payload(
        "https://hooks.slack.com/services/T000/B000/XYZ",
        "auto",
        "traffic_drop",
        "Recent traffic dropped compared with the previous lookback window.",
        "critical",
        {"current_value": 0.2, "threshold": 0.5},
    )

    assert payload["text"] == "[CRITICAL] traffic_drop"
    assert "blocks" in payload


def test_build_alert_payload_keeps_generic_shape_for_non_slack_webhooks() -> None:
    payload = _build_alert_payload(
        "https://example.com/webhook",
        "auto",
        "ingest_rejections",
        "Rejected ingest events exceed the configured threshold.",
        "warning",
        {"current_value": 2, "threshold": 0},
    )

    assert payload["severity"] == "warning"
    assert payload["title"] == "ingest_rejections"
    assert payload["attributes"] == {"current_value": 2, "threshold": 0}
