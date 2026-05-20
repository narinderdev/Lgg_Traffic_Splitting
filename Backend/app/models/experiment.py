from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entry_slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    entry_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="paused")
    traffic_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    segments: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    variants = relationship(
        "Variant",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="Variant.created_at",
        lazy="selectin",
    )
    impressions = relationship("Impression", back_populates="experiment", lazy="noload")
    conversions = relationship("Conversion", back_populates="experiment", lazy="noload")
