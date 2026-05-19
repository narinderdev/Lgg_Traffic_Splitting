from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Impression(Base):
    __tablename__ = "impressions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    traffic_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    experiment = relationship("Experiment", back_populates="impressions", lazy="noload")
    variant = relationship("Variant", back_populates="impressions", lazy="noload")
