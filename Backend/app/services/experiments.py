from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.experiment import Experiment
from app.models.impression import Impression
from app.models.variant import Variant
from app.schemas.common import DailyVariantCount, DimensionCount, StatsSummary, VariantImpressionCount
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.schemas.impression import ImpressionBatchIn
from app.services.cache import get_cache_value, invalidate_experiment_cache, set_cache_value


def _experiment_query() -> Select[tuple[Experiment]]:
    return select(Experiment).options(selectinload(Experiment.variants))


async def list_experiments(session: AsyncSession) -> list[Experiment]:
    query = _experiment_query().order_by(Experiment.updated_at.desc())
    result = await session.execute(query)
    return list(result.scalars().unique())


async def get_experiment_or_404(session: AsyncSession, experiment_id: UUID) -> Experiment:
    query = _experiment_query().where(Experiment.id == experiment_id)
    result = await session.execute(query)
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return experiment


async def create_experiment(session: AsyncSession, payload: ExperimentCreate) -> Experiment:
    experiment = Experiment(
        name=payload.name,
        entry_slug=payload.entry_slug,
        entry_url=str(payload.entry_url),
        status=payload.status.value,
        traffic_pct=payload.traffic_pct,
        segments=payload.segments.model_dump(mode="json"),
    )
    experiment.variants = [
        Variant(
            name=variant.name,
            destination_url=str(variant.destination_url),
            hyros_tag=variant.hyros_tag,
            weight=variant.weight,
            is_control=variant.is_control,
        )
        for variant in payload.variants
    ]
    session.add(experiment)
    await session.flush()
    return experiment


async def update_experiment(
    session: AsyncSession, experiment: Experiment, payload: ExperimentUpdate
) -> Experiment:
    changes = payload.model_dump(exclude_unset=True)

    if "name" in changes:
        experiment.name = changes["name"]
    if "entry_slug" in changes:
        experiment.entry_slug = changes["entry_slug"]
    if "entry_url" in changes:
        experiment.entry_url = str(changes["entry_url"])
    if "status" in changes:
        experiment.status = changes["status"].value
    if "traffic_pct" in changes:
        experiment.traffic_pct = changes["traffic_pct"]
    if "segments" in changes:
        experiment.segments = changes["segments"]
    if payload.variants is not None:
        existing_variants = {variant.id: variant for variant in experiment.variants}
        next_variants: list[Variant] = []

        for variant_input in payload.variants:
            if variant_input.id and variant_input.id in existing_variants:
                variant = existing_variants.pop(variant_input.id)
                variant.name = variant_input.name
                variant.destination_url = str(variant_input.destination_url)
                variant.hyros_tag = variant_input.hyros_tag
                variant.weight = variant_input.weight
                variant.is_control = variant_input.is_control
            else:
                variant = Variant(
                    id=variant_input.id,
                    name=variant_input.name,
                    destination_url=str(variant_input.destination_url),
                    hyros_tag=variant_input.hyros_tag,
                    weight=variant_input.weight,
                    is_control=variant_input.is_control,
                )
            next_variants.append(variant)

        experiment.variants = next_variants
    experiment.updated_at = datetime.now(UTC)

    await session.flush()
    await invalidate_experiment_cache(str(experiment.id))
    return experiment


async def delete_experiment(session: AsyncSession, experiment: Experiment) -> None:
    await session.delete(experiment)
    await invalidate_experiment_cache(str(experiment.id))


async def toggle_experiment(session: AsyncSession, experiment: Experiment, status_value: str) -> Experiment:
    experiment.status = status_value
    experiment.updated_at = datetime.now(UTC)
    await session.flush()
    await invalidate_experiment_cache(str(experiment.id))
    return experiment


async def ingest_impressions(session: AsyncSession, batch: ImpressionBatchIn) -> int:
    if not batch.events:
        return 0

    experiment_ids = {UUID(event.experiment_id) for event in batch.events}
    variant_ids = {UUID(event.variant_id) for event in batch.events}

    valid_pairs_query = select(Variant.id, Variant.experiment_id).where(
        Variant.id.in_(variant_ids),
        Variant.experiment_id.in_(experiment_ids),
    )
    valid_pairs = {
        (variant_id, experiment_id)
        for variant_id, experiment_id in (await session.execute(valid_pairs_query)).all()
    }

    payloads = [
        Impression(
            experiment_id=experiment_id,
            variant_id=variant_id,
            device_type=event.device_type.value if event.device_type else None,
            traffic_source=event.traffic_source.value if event.traffic_source else None,
            country=event.country,
            ts=event.ts or datetime.now(UTC),
        )
        for event in batch.events
        for experiment_id, variant_id in [(UUID(event.experiment_id), UUID(event.variant_id))]
        if (variant_id, experiment_id) in valid_pairs
    ]
    if not payloads:
        return 0

    session.add_all(payloads)
    touched_experiments = {event.experiment_id for event in batch.events}
    await session.flush()
    for experiment_id in touched_experiments:
        await invalidate_experiment_cache(experiment_id)
    return len(payloads)


async def get_stats_summary(session: AsyncSession, experiment: Experiment) -> StatsSummary:
    cache_key = f"experiment-stats:{experiment.id}:summary"
    cached = await get_cache_value(cache_key)
    if cached:
        return StatsSummary.model_validate(cached)

    totals_query = (
        select(
            Variant.id,
            Variant.name,
            Variant.is_control,
            func.count(Impression.id),
        )
        .select_from(Variant)
        .outerjoin(Impression, Impression.variant_id == Variant.id)
        .where(Variant.experiment_id == experiment.id)
        .group_by(Variant.id, Variant.name, Variant.is_control)
        .order_by(Variant.created_at.asc())
    )
    totals_rows = (await session.execute(totals_query)).all()

    device_query = (
        select(
            func.coalesce(Impression.device_type, "unknown"),
            func.count(Impression.id),
        )
        .where(Impression.experiment_id == experiment.id)
        .group_by(Impression.device_type)
        .order_by(func.count(Impression.id).desc())
    )
    source_query = (
        select(
            func.coalesce(Impression.traffic_source, "unknown"),
            func.count(Impression.id),
        )
        .where(Impression.experiment_id == experiment.id)
        .group_by(Impression.traffic_source)
        .order_by(func.count(Impression.id).desc())
    )

    devices_rows = (await session.execute(device_query)).all()
    source_rows = (await session.execute(source_query)).all()

    summary = StatsSummary(
        experiment_id=str(experiment.id),
        totals=[
            VariantImpressionCount(
                variant_id=str(variant_id),
                variant_name=name,
                is_control=is_control,
                count=count,
            )
            for variant_id, name, is_control, count in totals_rows
        ],
        by_device_type=[
            DimensionCount(dimension=str(dimension), count=count) for dimension, count in devices_rows
        ],
        by_traffic_source=[
            DimensionCount(dimension=str(dimension), count=count) for dimension, count in source_rows
        ],
        generated_at=datetime.now(UTC),
    )
    await set_cache_value(cache_key, summary.model_dump(mode="json"))
    return summary


async def get_daily_stats(
    session: AsyncSession,
    experiment: Experiment,
    start_date: date | None,
    end_date: date | None,
) -> list[DailyVariantCount]:
    resolved_end = end_date or datetime.now(UTC).date()
    resolved_start = start_date or (resolved_end - timedelta(days=13))
    cache_key = (
        f"experiment-stats:{experiment.id}:daily:{resolved_start.isoformat()}:{resolved_end.isoformat()}"
    )
    cached = await get_cache_value(cache_key)
    if cached:
        return [DailyVariantCount.model_validate(item) for item in cached]

    start_ts = datetime.combine(resolved_start, time.min, tzinfo=UTC)
    end_ts = datetime.combine(resolved_end + timedelta(days=1), time.min, tzinfo=UTC)

    query = (
        select(
            func.date_trunc("day", Impression.ts).label("day"),
            Variant.id,
            Variant.name,
            func.count(Impression.id),
        )
        .join(Variant, Variant.id == Impression.variant_id)
        .where(Impression.experiment_id == experiment.id)
        .where(Impression.ts >= start_ts, Impression.ts < end_ts)
        .group_by("day", Variant.id, Variant.name)
        .order_by("day", Variant.name)
    )
    rows = (await session.execute(query)).all()
    results = [
        DailyVariantCount(
            day=day.date(),
            variant_id=str(variant_id),
            variant_name=name,
            count=count,
        )
        for day, variant_id, name, count in rows
    ]
    await set_cache_value(cache_key, [item.model_dump(mode="json") for item in results])
    return results
