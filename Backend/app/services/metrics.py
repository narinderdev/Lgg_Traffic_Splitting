from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "traffic_splitting_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "traffic_splitting_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)
INGEST_COUNT = Counter(
    "traffic_splitting_ingest_events_total",
    "Ingested event count",
    ["kind"],
)
INGEST_REJECTED_COUNT = Counter(
    "traffic_splitting_ingest_rejected_events_total",
    "Rejected ingest event count",
    ["kind"],
)
CLOUDFLARE_SYNC_COUNT = Counter(
    "traffic_splitting_cloudflare_sync_total",
    "Cloudflare KV sync attempts",
    ["operation", "status"],
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


def get_counter_value(counter: Counter, **labels: str) -> int:
    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name != f"{counter._name}_total":
                continue
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                return int(sample.value)
    return 0
