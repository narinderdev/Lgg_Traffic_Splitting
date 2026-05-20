from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.core.security import require_admin_api_key
from app.schemas.common import DailyVariantCount, StatsSummary
from app.schemas.common import MultivariatePreviewRequest, MultivariatePreviewVariant
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentListItem,
    ExperimentRead,
    ExperimentUpdate,
    ToggleExperimentRequest,
)
from app.services.cloudflare import delete_experiment_config, upsert_experiment_config
from app.services.experiments import (
    create_experiment,
    build_multivariate_preview,
    delete_experiment,
    get_daily_stats,
    get_experiment_or_404,
    get_stats_summary,
    list_experiments,
    toggle_experiment,
    update_experiment,
)

router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.get("", response_model=list[ExperimentListItem])
async def list_all_experiments(session: AsyncSession = Depends(db_session)) -> list[ExperimentListItem]:
    experiments = await list_experiments(session)
    return [ExperimentListItem.model_validate(experiment) for experiment in experiments]


@router.post("", response_model=ExperimentRead, status_code=status.HTTP_201_CREATED)
async def create_experiment_endpoint(
    payload: ExperimentCreate,
    session: AsyncSession = Depends(db_session),
) -> ExperimentRead:
    experiment = await create_experiment(session, payload)
    await session.commit()
    persisted_experiment = await get_experiment_or_404(session, experiment.id)
    await upsert_experiment_config(persisted_experiment)
    return ExperimentRead.model_validate(persisted_experiment)


@router.get("/{experiment_id}", response_model=ExperimentRead)
async def get_experiment_endpoint(
    experiment_id: UUID,
    session: AsyncSession = Depends(db_session),
) -> ExperimentRead:
    experiment = await get_experiment_or_404(session, experiment_id)
    return ExperimentRead.model_validate(experiment)


@router.patch("/{experiment_id}", response_model=ExperimentRead)
async def update_experiment_endpoint(
    experiment_id: UUID,
    payload: ExperimentUpdate,
    session: AsyncSession = Depends(db_session),
) -> ExperimentRead:
    experiment = await get_experiment_or_404(session, experiment_id)
    experiment = await update_experiment(session, experiment, payload)
    await session.commit()
    persisted_experiment = await get_experiment_or_404(session, experiment.id)
    await upsert_experiment_config(persisted_experiment)
    return ExperimentRead.model_validate(persisted_experiment)


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment_endpoint(
    experiment_id: UUID,
    session: AsyncSession = Depends(db_session),
) -> Response:
    experiment = await get_experiment_or_404(session, experiment_id)
    entry_slug = experiment.entry_slug
    await delete_experiment(session, experiment)
    await session.commit()
    await delete_experiment_config(entry_slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{experiment_id}/toggle", response_model=ExperimentRead)
async def toggle_experiment_endpoint(
    experiment_id: UUID,
    payload: ToggleExperimentRequest,
    session: AsyncSession = Depends(db_session),
) -> ExperimentRead:
    experiment = await get_experiment_or_404(session, experiment_id)
    next_status = payload.status.value if payload.status else ("paused" if experiment.status == "active" else "active")
    experiment = await toggle_experiment(session, experiment, next_status)
    await session.commit()
    persisted_experiment = await get_experiment_or_404(session, experiment.id)
    await upsert_experiment_config(persisted_experiment)
    return ExperimentRead.model_validate(persisted_experiment)


@router.get("/{experiment_id}/stats", response_model=StatsSummary)
async def experiment_stats_endpoint(
    experiment_id: UUID,
    session: AsyncSession = Depends(db_session),
) -> StatsSummary:
    experiment = await get_experiment_or_404(session, experiment_id)
    return await get_stats_summary(session, experiment)


@router.get("/{experiment_id}/stats/daily", response_model=list[DailyVariantCount])
async def experiment_daily_stats_endpoint(
    experiment_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(db_session),
) -> list[DailyVariantCount]:
    experiment = await get_experiment_or_404(session, experiment_id)
    return await get_daily_stats(session, experiment, start_date, end_date)


@router.post("/multivariate/preview", response_model=list[MultivariatePreviewVariant])
async def multivariate_preview_endpoint(
    payload: MultivariatePreviewRequest,
) -> list[MultivariatePreviewVariant]:
    return build_multivariate_preview(payload)
