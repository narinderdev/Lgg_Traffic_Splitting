from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExperimentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class DeviceType(StrEnum):
    MOBILE = "mobile"
    DESKTOP = "desktop"
    TABLET = "tablet"


class TrafficSource(StrEnum):
    PAID_SEARCH = "paid_search"
    SOCIAL = "social"
    DIRECT = "direct"
    ORGANIC = "organic"
    UNKNOWN = "unknown"


class Segments(ORMModel):
    device_types: list[DeviceType] = Field(default_factory=list)
    traffic_sources: list[TrafficSource] = Field(default_factory=list)


class VariantBase(ORMModel):
    name: str = Field(min_length=1, max_length=120)
    destination_url: HttpUrl
    hyros_tag: str | None = Field(default=None, max_length=255)
    weight: int = Field(ge=0, le=100)
    is_control: bool = False


class VariantCreate(VariantBase):
    pass


class VariantUpdate(VariantBase):
    id: UUID | None = None


class VariantRead(VariantBase):
    id: UUID
    created_at: datetime


class DimensionCount(ORMModel):
    dimension: str
    count: int


class VariantImpressionCount(ORMModel):
    variant_id: UUID
    variant_name: str
    is_control: bool
    count: int


class DailyVariantCount(ORMModel):
    day: date
    variant_id: UUID
    variant_name: str
    count: int


class StatsSummary(ORMModel):
    experiment_id: UUID
    totals: list[VariantImpressionCount]
    by_device_type: list[DimensionCount]
    by_traffic_source: list[DimensionCount]
    generated_at: datetime
