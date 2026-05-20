from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.experiments import router as experiments_router
from app.api.routes.health import router as health_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.monitoring import router as monitoring_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(metrics_router)
api_router.include_router(monitoring_router)
api_router.include_router(experiments_router)
api_router.include_router(ingest_router)
