from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.schemas.common import (
    ExperimentStatus,
    ORMModel,
    Segments,
    VariantCreate,
    VariantRead,
    VariantUpdate,
)


class ExperimentBase(ORMModel):
    name: str = Field(min_length=1, max_length=160)
    entry_slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    entry_url: HttpUrl
    status: ExperimentStatus = ExperimentStatus.PAUSED
    traffic_pct: int = Field(default=100, ge=0, le=100)
    segments: Segments = Field(default_factory=Segments)


class ExperimentCreate(ExperimentBase):
    variants: list[VariantCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_variants(self) -> "ExperimentCreate":
        _validate_variant_collection(self.variants)
        return self


class ExperimentUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    entry_slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    entry_url: HttpUrl | None = None
    status: ExperimentStatus | None = None
    traffic_pct: int | None = Field(default=None, ge=0, le=100)
    segments: Segments | None = None
    variants: list[VariantUpdate] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_variants(self) -> "ExperimentUpdate":
        if self.variants is not None:
            _validate_variant_collection(self.variants)
        return self


class ExperimentRead(ExperimentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    variants: list[VariantRead]


class ExperimentListItem(ExperimentRead):
    total_impressions: int = 0


class ToggleExperimentRequest(ORMModel):
    status: ExperimentStatus | None = None


def _validate_variant_collection(variants: list[VariantCreate | VariantUpdate]) -> None:
    total_weight = sum(variant.weight for variant in variants)
    if total_weight != 100:
        raise ValueError("Variant weights must sum to 100")

    control_variants = [variant for variant in variants if variant.is_control]
    if len(control_variants) != 1:
        raise ValueError("Exactly one control variant is required")
