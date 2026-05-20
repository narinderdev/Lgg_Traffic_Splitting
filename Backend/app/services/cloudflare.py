from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.models.experiment import Experiment
from app.services.alerts import send_alert
from app.services.metrics import CLOUDFLARE_SYNC_COUNT

settings = get_settings()


def serialize_experiment_for_edge(experiment: Experiment) -> dict[str, Any]:
    return {
        "id": str(experiment.id),
        "name": experiment.name,
        "entry_slug": experiment.entry_slug,
        "entry_url": experiment.entry_url,
        "status": experiment.status,
        "traffic_pct": experiment.traffic_pct,
        "segments": experiment.segments,
        "variants": [
            {
                "id": str(variant.id),
                "name": variant.name,
                "destination_url": variant.destination_url,
                "hyros_tag": variant.hyros_tag,
                "weight": variant.weight,
                "is_control": variant.is_control,
                "metadata": variant.routing_metadata,
            }
            for variant in experiment.variants
        ],
    }


async def upsert_experiment_config(experiment: Experiment) -> None:
    if not settings.cloudflare_sync_enabled:
        return

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.cloudflare_account_id}/storage/kv/namespaces/"
        f"{settings.cloudflare_kv_namespace_id}/values/experiment:{experiment.entry_slug}"
    )
    headers = {
        "Authorization": f"Bearer {settings.cloudflare_api_token}",
        "Content-Type": "application/json",
    }
    payload = serialize_experiment_for_edge(experiment)

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.put(url, headers=headers, json=payload)
            response.raise_for_status()
            CLOUDFLARE_SYNC_COUNT.labels("upsert", "success").inc()
        except Exception as exc:
            CLOUDFLARE_SYNC_COUNT.labels("upsert", "failure").inc()
            await send_alert(
                "Cloudflare experiment sync failed",
                f"entry_slug={experiment.entry_slug}\nerror={exc}",
            )
            raise


async def delete_experiment_config(entry_slug: str) -> None:
    if not settings.cloudflare_sync_enabled:
        return

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.cloudflare_account_id}/storage/kv/namespaces/"
        f"{settings.cloudflare_kv_namespace_id}/values/experiment:{entry_slug}"
    )
    headers = {"Authorization": f"Bearer {settings.cloudflare_api_token}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()
            CLOUDFLARE_SYNC_COUNT.labels("delete", "success").inc()
        except Exception as exc:
            CLOUDFLARE_SYNC_COUNT.labels("delete", "failure").inc()
            await send_alert(
                "Cloudflare experiment delete failed",
                f"entry_slug={entry_slug}\nerror={exc}",
            )
            raise
