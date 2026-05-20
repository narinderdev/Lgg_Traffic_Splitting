"""partition impressions and add rollups

Revision ID: 20260519_000002
Revises: 20260519_000001
Create Date: 2026-05-19 20:30:00
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260519_000002"
down_revision = "20260519_000001"
branch_labels = None
depends_on = None


def _month_floor(value: date) -> date:
    return value.replace(day=1)


def _add_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _create_partition(month_start: date) -> None:
    next_month = _add_month(month_start)
    partition_name = f"impressions_{month_start.year}{month_start.month:02d}"
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF impressions
        FOR VALUES FROM ('{month_start.isoformat()}') TO ('{next_month.isoformat()}')
        """
    )


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("CREATE SEQUENCE IF NOT EXISTS impressions_id_seq AS BIGINT;")
    op.rename_table("impressions", "impressions_legacy")
    op.execute(
        "ALTER TABLE impressions_legacy RENAME CONSTRAINT impressions_pkey TO impressions_legacy_pkey"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_impressions_experiment_ts RENAME TO idx_impressions_experiment_ts_legacy"
    )
    op.execute("ALTER INDEX IF EXISTS idx_impressions_variant RENAME TO idx_impressions_variant_legacy")

    op.execute(
        """
        CREATE TABLE impressions (
            id BIGINT NOT NULL DEFAULT nextval('impressions_id_seq'),
            experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
            variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
            device_type TEXT NULL,
            traffic_source TEXT NULL,
            country TEXT NULL,
            ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts)
        """
    )

    min_ts, max_ts = bind.execute(sa.text("SELECT min(ts), max(ts) FROM impressions_legacy")).one()
    if min_ts is None or max_ts is None:
        current_month = _month_floor(datetime.now(UTC).date())
        months = [current_month, _add_month(current_month)]
    else:
        month = _month_floor(min_ts.astimezone(UTC).date())
        end_month = _add_month(_month_floor(max_ts.astimezone(UTC).date()))
        months = []
        while month <= end_month:
            months.append(month)
            month = _add_month(month)

    for month_start in months:
        _create_partition(month_start)

    op.create_index("idx_impressions_experiment_ts", "impressions", ["experiment_id", "ts"], unique=False)
    op.create_index("idx_impressions_variant", "impressions", ["variant_id"], unique=False)

    op.execute(
        """
        INSERT INTO impressions (id, experiment_id, variant_id, device_type, traffic_source, country, ts)
        SELECT id, experiment_id, variant_id, device_type, traffic_source, country, ts
        FROM impressions_legacy
        ORDER BY id
        """
    )
    op.execute(
        """
        SELECT setval(
            'impressions_id_seq',
            COALESCE((SELECT MAX(id) FROM impressions), 1),
            true
        )
        """
    )

    op.create_table(
        "impression_daily_rollups",
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("device_type", sa.Text(), primary_key=True),
        sa.Column("traffic_source", sa.Text(), primary_key=True),
        sa.Column("count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "idx_impression_daily_rollups_experiment_day",
        "impression_daily_rollups",
        ["experiment_id", "day"],
        unique=False,
    )
    op.create_index(
        "idx_impression_daily_rollups_variant_day",
        "impression_daily_rollups",
        ["variant_id", "day"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO impression_daily_rollups (
            experiment_id,
            variant_id,
            day,
            device_type,
            traffic_source,
            count
        )
        SELECT
            experiment_id,
            variant_id,
            DATE(timezone('UTC', ts)) AS day,
            COALESCE(device_type, 'unknown') AS device_type,
            COALESCE(traffic_source, 'unknown') AS traffic_source,
            COUNT(*) AS count
        FROM impressions
        GROUP BY
            experiment_id,
            variant_id,
            DATE(timezone('UTC', ts)),
            COALESCE(device_type, 'unknown'),
            COALESCE(traffic_source, 'unknown')
        """
    )

    op.execute("ALTER TABLE impressions_legacy ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER SEQUENCE impressions_id_seq OWNED BY NONE")
    op.drop_table("impressions_legacy")


def downgrade() -> None:
    op.drop_index("idx_impression_daily_rollups_variant_day", table_name="impression_daily_rollups")
    op.drop_index("idx_impression_daily_rollups_experiment_day", table_name="impression_daily_rollups")
    op.drop_table("impression_daily_rollups")

    op.rename_table("impressions", "impressions_partitioned")
    op.execute(
        "ALTER TABLE impressions_partitioned RENAME CONSTRAINT impressions_pkey TO impressions_partitioned_pkey"
    )
    op.drop_index("idx_impressions_variant", table_name="impressions_partitioned")
    op.drop_index("idx_impressions_experiment_ts", table_name="impressions_partitioned")

    op.create_table(
        "impressions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_type", sa.Text(), nullable=True),
        sa.Column("traffic_source", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_impressions_experiment_ts", "impressions", ["experiment_id", "ts"], unique=False)
    op.create_index("idx_impressions_variant", "impressions", ["variant_id"], unique=False)

    op.execute(
        """
        INSERT INTO impressions (id, experiment_id, variant_id, device_type, traffic_source, country, ts)
        SELECT id, experiment_id, variant_id, device_type, traffic_source, country, ts
        FROM impressions_partitioned
        ORDER BY id
        """
    )

    op.execute("ALTER TABLE impressions_partitioned ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER SEQUENCE impressions_id_seq OWNED BY NONE")
    op.execute("DROP TABLE impressions_partitioned CASCADE")
