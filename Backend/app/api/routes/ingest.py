from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.core.security import require_ingest_api_key
from app.schemas.impression import (
    ConversionBatchIn,
    ConversionBatchResult,
    ImpressionBatchIn,
    ImpressionBatchResult,
)
from app.services.experiments import ingest_conversions, ingest_impressions

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/impressions",
    response_model=ImpressionBatchResult,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_ingest_api_key)],
)
async def ingest_impressions_endpoint(
    payload: ImpressionBatchIn,
    session: AsyncSession = Depends(db_session),
) -> ImpressionBatchResult:
    inserted = await ingest_impressions(session, payload)
    await session.commit()
    return ImpressionBatchResult(inserted=inserted)


@router.post(
    "/conversions",
    response_model=ConversionBatchResult,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_ingest_api_key)],
)
async def ingest_conversions_endpoint(
    payload: ConversionBatchIn,
    session: AsyncSession = Depends(db_session),
) -> ConversionBatchResult:
    inserted = await ingest_conversions(session, payload)
    await session.commit()
    return ConversionBatchResult(inserted=inserted)
