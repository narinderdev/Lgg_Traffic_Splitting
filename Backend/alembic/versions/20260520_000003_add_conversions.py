"""add conversions

Revision ID: 20260520_000003
Revises: 20260519_000002
Create Date: 2026-05-20 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260520_000003"
down_revision = "20260519_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversions",
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
        sa.Column("conversion_type", sa.Text(), nullable=False),
        sa.Column("visitor_id", sa.Text(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_conversions_experiment_ts", "conversions", ["experiment_id", "ts"], unique=False)
    op.create_index("idx_conversions_variant_type", "conversions", ["variant_id", "conversion_type"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_conversions_variant_type", table_name="conversions")
    op.drop_index("idx_conversions_experiment_ts", table_name="conversions")
    op.drop_table("conversions")
