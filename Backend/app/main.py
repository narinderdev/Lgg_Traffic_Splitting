from __future__ import annotations

import logging
from time import perf_counter

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from starlette.requests import Request

from app.api.router import api_router
from app.core.config import get_settings
from app.services.metrics import REQUEST_COUNT, REQUEST_LATENCY

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("traffic_splitting.api")

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        send_default_pii=True,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[FastApiIntegration()],
    )

app = FastAPI(
    title="Traffic Splitting API",
    version="0.1.0",
    description="Management plane for the internal URL split testing tool.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    start = perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = perf_counter() - start
        status_code = response.status_code if response is not None else 500
        path = request.url.path
        REQUEST_COUNT.labels(request.method, path, str(status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
        logger.info(
            "request_complete",
            extra={
                "method": request.method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round(elapsed * 1000, 2),
            },
        )


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"name": "traffic-splitting-api", "status": "ok"}
