from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _month_floor(value: date) -> date:
    return value.replace(day=1)


def _add_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _partition_name(month_start: date) -> str:
    return f"impressions_{month_start.year}{month_start.month:02d}"


async def ensure_impression_partitions(
    session: AsyncSession,
    timestamps: list[datetime] | tuple[datetime, ...],
) -> None:
    if not timestamps:
        return

    months: set[date] = set()
    for timestamp in timestamps:
        month_start = _month_floor(timestamp.astimezone(UTC).date())
        months.add(month_start)
        months.add(_add_month(month_start))

    for month_start in sorted(months):
        next_month = _add_month(month_start)
        partition_name = _partition_name(month_start)
        await session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF impressions
                FOR VALUES FROM ('{month_start.isoformat()}') TO ('{next_month.isoformat()}')
                """
            ),
        )
