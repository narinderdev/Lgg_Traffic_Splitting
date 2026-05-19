"""initial schema

Revision ID: 20260519_000001
Revises:
Create Date: 2026-05-19 17:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260519_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("entry_slug", sa.Text(), nullable=False, unique=True),
        sa.Column("entry_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="paused"),
        sa.Column("traffic_pct", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("segments", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("hyros_tag", sa.Text(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("is_control", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "impressions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_type", sa.Text(), nullable=True),
        sa.Column("traffic_source", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("idx_impressions_experiment_ts", "impressions", ["experiment_id", "ts"], unique=False)
    op.create_index("idx_impressions_variant", "impressions", ["variant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_impressions_variant", table_name="impressions")
    op.drop_index("idx_impressions_experiment_ts", table_name="impressions")
    op.drop_table("impressions")
    op.drop_table("variants")
    op.drop_table("experiments")
