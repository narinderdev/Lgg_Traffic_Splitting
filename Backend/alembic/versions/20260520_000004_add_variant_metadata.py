"""add variant metadata

Revision ID: 20260520_000004
Revises: 20260520_000003
Create Date: 2026-05-20 10:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260520_000004"
down_revision = "20260520_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "variants",
        sa.Column(
            "routing_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("variants", "routing_metadata")
