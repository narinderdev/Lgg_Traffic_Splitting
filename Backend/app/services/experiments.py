from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from itertools import product
from math import erf, sqrt
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversion import Conversion
from app.models.experiment import Experiment
from app.models.impression import Impression
from app.models.impression_rollup import ImpressionDailyRollup
from app.models.variant import Variant
from app.schemas.common import (
    DailyVariantCount,
    DimensionCount,
    MultivariateFactor,
    MultivariatePreviewRequest,
    MultivariatePreviewVariant,
    StatsSummary,
    VariantConversionCount,
    VariantImpressionCount,
)
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.schemas.impression import ConversionBatchIn, ImpressionBatchIn
from app.services.cache import get_cache_value, invalidate_experiment_cache, set_cache_value
from app.services.metrics import INGEST_COUNT, INGEST_REJECTED_COUNT
from app.services.partitions import ensure_impression_partitions


def _experiment_query() -> Select[tuple[Experiment]]:
    return select(Experiment).options(selectinload(Experiment.variants))


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def _compute_significance(
    impressions: int,
    conversions: int,
    control_impressions: int,
    control_conversions: int,
) -> tuple[float | None, float | None, bool]:
    if impressions <= 0 or control_impressions <= 0:
        return None, None, False

    rate = conversions / impressions
    control_rate = control_conversions / control_impressions
    pooled_numerator = conversions + control_conversions
    pooled_denominator = impressions + control_impressions

    if pooled_denominator == 0:
        return None, None, False

    pooled_rate = pooled_numerator / pooled_denominator
    variance = pooled_rate * (1 - pooled_rate) * ((1 / impressions) + (1 / control_impressions))
    if variance <= 0:
        return None, None, False

    z_score = (rate - control_rate) / sqrt(variance)
    p_value = max(0.0, min(1.0, 2 * (1 - _normal_cdf(abs(z_score)))))
    return z_score, p_value, p_value < 0.05


def _build_conversion_stats(
    totals_rows: list[tuple[UUID, str, bool, int]],
    conversion_rows: list[tuple[UUID, str, bool, int]],
) -> list[VariantConversionCount]:
    impression_counts = {variant_id: int(count) for variant_id, _, _, count in totals_rows}
    conversions_by_variant = {
        variant_id: (name, is_control, int(conversions))
        for variant_id, name, is_control, conversions in conversion_rows
    }
    control_row = next((row for row in conversion_rows if row[2]), None)
    control_variant_id = control_row[0] if control_row else None
    control_impressions = impression_counts.get(control_variant_id, 0) if control_variant_id else 0
    control_conversions = int(control_row[3]) if control_row else 0
    control_rate = (
        (control_conversions / control_impressions)
        if control_variant_id and control_impressions > 0
        else None
    )

    stats: list[VariantConversionCount] = []
    for variant_id, name, is_control, _count in totals_rows:
        _, _, conversions = conversions_by_variant.get(variant_id, (name, is_control, 0))
        impressions = impression_counts.get(variant_id, 0)
        conversion_rate = (conversions / impressions) if impressions > 0 else 0.0
        z_score = p_value = None
        is_significant = False
        uplift_vs_control = None

        if control_variant_id and variant_id != control_variant_id:
            z_score, p_value, is_significant = _compute_significance(
                impressions,
                conversions,
                control_impressions,
                control_conversions,
            )
            if control_rate and control_rate > 0:
                uplift_vs_control = (conversion_rate - control_rate) / control_rate

        stats.append(
            VariantConversionCount(
                variant_id=str(variant_id),
                variant_name=name,
                is_control=is_control,
                conversions=conversions,
                conversion_rate=conversion_rate,
                uplift_vs_control=uplift_vs_control,
                z_score=z_score,
                p_value=p_value,
                is_significant=is_significant,
            )
        )

    return stats


def build_multivariate_preview(payload: MultivariatePreviewRequest) -> list[MultivariatePreviewVariant]:
    factors: list[MultivariateFactor] = payload.factors
    option_sets = [factor.options for factor in factors]
    combinations = list(product(*option_sets))
    if not combinations:
        return []

    base_weight = 100 // len(combinations)
    remainder = 100 - (base_weight * len(combinations))
    variants: list[MultivariatePreviewVariant] = []

    for index, combo in enumerate(combinations):
        assignments = {factor.key: option.key for factor, option in zip(factors, combo, strict=True)}
        label = " / ".join(option.label for option in combo)
        hyros_bits = [payload.hyros_tag_prefix] if payload.hyros_tag_prefix else []
        hyros_bits.extend(option.key for option in combo)
        weight = base_weight + (1 if index < remainder else 0)

        variants.append(
            MultivariatePreviewVariant(
                name=label,
                destination_url=payload.destination_url,
                hyros_tag="-".join(bit for bit in hyros_bits if bit),
                weight=weight,
                is_control=index == 0,
                routing_metadata={
                    "multivariate": True,
                    "multivariate_values": assignments,
                },
                factor_assignments=assignments,
            )
        )

    return variants


async def list_experiments(session: AsyncSession) -> list[Experiment]:
    totals_subquery = (
        select(
            ImpressionDailyRollup.experiment_id.label("experiment_id"),
            func.sum(ImpressionDailyRollup.count).label("total_impressions"),
        )
        .group_by(ImpressionDailyRollup.experiment_id)
        .subquery()
    )
    query = (
        select(Experiment, func.coalesce(totals_subquery.c.total_impressions, 0))
        .options(selectinload(Experiment.variants))
        .outerjoin(totals_subquery, totals_subquery.c.experiment_id == Experiment.id)
        .order_by(Experiment.updated_at.desc())
    )
    result = await session.execute(query)
    experiments: list[Experiment] = []
    for experiment, total_impressions in result.unique().all():
        setattr(experiment, "total_impressions", int(total_impressions or 0))
        experiments.append(experiment)
    return experiments


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
            routing_metadata=variant.routing_metadata,
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
                variant.routing_metadata = variant_input.routing_metadata
            else:
                variant = Variant(
                    id=variant_input.id,
                    name=variant_input.name,
                    destination_url=str(variant_input.destination_url),
                    hyros_tag=variant_input.hyros_tag,
                    weight=variant_input.weight,
                    is_control=variant_input.is_control,
                    routing_metadata=variant_input.routing_metadata,
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
    rejected_events = len(batch.events) - sum(
        1
        for event in batch.events
        if (UUID(event.variant_id), UUID(event.experiment_id)) in valid_pairs
    )
    if rejected_events:
        INGEST_REJECTED_COUNT.labels("impression").inc(rejected_events)

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

    await ensure_impression_partitions(session, [payload.ts for payload in payloads])
    session.add_all(payloads)
    rollup_counts: Counter[tuple[UUID, UUID, date, str, str]] = Counter()
    touched_experiments: set[str] = set()

    for event in batch.events:
        experiment_id = UUID(event.experiment_id)
        variant_id = UUID(event.variant_id)
        if (variant_id, experiment_id) not in valid_pairs:
            continue

        event_ts = event.ts or datetime.now(UTC)
        rollup_counts[
            (
                experiment_id,
                variant_id,
                event_ts.date(),
                event.device_type.value if event.device_type else "unknown",
                event.traffic_source.value if event.traffic_source else "unknown",
            )
        ] += 1
        touched_experiments.add(str(experiment_id))

    if rollup_counts:
        rollup_insert = pg_insert(ImpressionDailyRollup).values(
            [
                {
                    "experiment_id": experiment_id,
                    "variant_id": variant_id,
                    "day": rollup_day,
                    "device_type": device_type,
                    "traffic_source": traffic_source,
                    "count": count,
                }
                for (experiment_id, variant_id, rollup_day, device_type, traffic_source), count in rollup_counts.items()
            ]
        )
        await session.execute(
            rollup_insert.on_conflict_do_update(
                index_elements=[
                    ImpressionDailyRollup.experiment_id,
                    ImpressionDailyRollup.variant_id,
                    ImpressionDailyRollup.day,
                    ImpressionDailyRollup.device_type,
                    ImpressionDailyRollup.traffic_source,
                ],
                set_={
                    "count": ImpressionDailyRollup.count + rollup_insert.excluded.count,
                    "updated_at": func.now(),
                },
            )
        )

    await session.flush()
    INGEST_COUNT.labels("impression").inc(len(payloads))
    for experiment_id in touched_experiments:
        await invalidate_experiment_cache(experiment_id)
    return len(payloads)


async def ingest_conversions(session: AsyncSession, batch: ConversionBatchIn) -> int:
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
    rejected_events = len(batch.events) - sum(
        1
        for event in batch.events
        if (UUID(event.variant_id), UUID(event.experiment_id)) in valid_pairs
    )
    if rejected_events:
        INGEST_REJECTED_COUNT.labels("conversion").inc(rejected_events)

    payloads = [
        Conversion(
            experiment_id=experiment_id,
            variant_id=variant_id,
            conversion_type=event.conversion_type,
            visitor_id=event.visitor_id,
            ts=event.ts or datetime.now(UTC),
        )
        for event in batch.events
        for experiment_id, variant_id in [(UUID(event.experiment_id), UUID(event.variant_id))]
        if (variant_id, experiment_id) in valid_pairs
    ]
    if not payloads:
        return 0

    session.add_all(payloads)
    await session.flush()
    INGEST_COUNT.labels("conversion").inc(len(payloads))
    for experiment_id in {event.experiment_id for event in batch.events}:
        await invalidate_experiment_cache(experiment_id)
    return len(payloads)


async def get_stats_summary(session: AsyncSession, experiment: Experiment) -> StatsSummary:
    cache_key = f"experiment-stats:{experiment.id}:summary"
    cached = await get_cache_value(cache_key)
    if cached:
        return StatsSummary.model_validate(cached)

    totals_subquery = (
        select(
            ImpressionDailyRollup.variant_id.label("variant_id"),
            func.sum(ImpressionDailyRollup.count).label("count"),
        )
        .where(ImpressionDailyRollup.experiment_id == experiment.id)
        .group_by(ImpressionDailyRollup.variant_id)
        .subquery()
    )
    totals_query = (
        select(
            Variant.id,
            Variant.name,
            Variant.is_control,
            func.coalesce(totals_subquery.c.count, 0),
        )
        .select_from(Variant)
        .outerjoin(totals_subquery, totals_subquery.c.variant_id == Variant.id)
        .where(Variant.experiment_id == experiment.id)
        .order_by(Variant.created_at.asc())
    )
    totals_rows = (await session.execute(totals_query)).all()

    device_query = (
        select(
            ImpressionDailyRollup.device_type,
            func.sum(ImpressionDailyRollup.count),
        )
        .where(ImpressionDailyRollup.experiment_id == experiment.id)
        .group_by(ImpressionDailyRollup.device_type)
        .order_by(func.sum(ImpressionDailyRollup.count).desc())
    )
    source_query = (
        select(
            ImpressionDailyRollup.traffic_source,
            func.sum(ImpressionDailyRollup.count),
        )
        .where(ImpressionDailyRollup.experiment_id == experiment.id)
        .group_by(ImpressionDailyRollup.traffic_source)
        .order_by(func.sum(ImpressionDailyRollup.count).desc())
    )

    devices_rows = (await session.execute(device_query)).all()
    source_rows = (await session.execute(source_query)).all()

    conversion_rows = (
        await session.execute(
            select(
                Variant.id,
                Variant.name,
                Variant.is_control,
                func.count(Conversion.id),
            )
            .select_from(Variant)
            .outerjoin(Conversion, Conversion.variant_id == Variant.id)
            .where(Variant.experiment_id == experiment.id)
            .group_by(Variant.id, Variant.name, Variant.is_control)
            .order_by(Variant.created_at.asc())
        )
    ).all()

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
        conversions=_build_conversion_stats(totals_rows, conversion_rows),
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

    query = (
        select(
            ImpressionDailyRollup.day,
            ImpressionDailyRollup.variant_id,
            Variant.name,
            func.sum(ImpressionDailyRollup.count),
        )
        .select_from(ImpressionDailyRollup)
        .join(Variant, Variant.id == ImpressionDailyRollup.variant_id)
        .where(
            ImpressionDailyRollup.experiment_id == experiment.id,
            ImpressionDailyRollup.day >= resolved_start,
            ImpressionDailyRollup.day <= resolved_end,
        )
        .group_by(
            ImpressionDailyRollup.day,
            ImpressionDailyRollup.variant_id,
            Variant.name,
        )
        .order_by(ImpressionDailyRollup.day.asc(), Variant.name.asc())
    )
    rows = (await session.execute(query)).all()
    results = [
        DailyVariantCount(
            day=day,
            variant_id=str(variant_id),
            variant_name=name,
            count=count,
        )
        for day, variant_id, name, count in rows
    ]
    await set_cache_value(cache_key, [item.model_dump(mode="json") for item in results])
    return results
