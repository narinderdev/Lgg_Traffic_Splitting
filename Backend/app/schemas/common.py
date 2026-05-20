from __future__ import annotations

from typing import Any
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl


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
    routing_metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("routing_metadata", "metadata"),
        serialization_alias="metadata",
    )


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


class VariantConversionCount(ORMModel):
    variant_id: UUID
    variant_name: str
    is_control: bool
    conversions: int
    conversion_rate: float
    uplift_vs_control: float | None = None
    z_score: float | None = None
    p_value: float | None = None
    is_significant: bool = False


class DailyVariantCount(ORMModel):
    day: date
    variant_id: UUID
    variant_name: str
    count: int


class StatsSummary(ORMModel):
    experiment_id: UUID
    totals: list[VariantImpressionCount]
    conversions: list[VariantConversionCount] = Field(default_factory=list)
    by_device_type: list[DimensionCount]
    by_traffic_source: list[DimensionCount]
    generated_at: datetime


class MonitoringAlert(ORMModel):
    code: str
    severity: str
    message: str
    current_value: float | int | None = None
    threshold: float | int | None = None


class MonitoringThresholds(ORMModel):
    lookback_minutes: int
    min_recent_impressions: int
    min_traffic_ratio: float
    max_ingest_rejections: int
    max_cloudflare_sync_failures: int


class MonitoringSummary(ORMModel):
    generated_at: datetime
    lookback_minutes: int
    recent_impressions: int
    previous_impressions: int
    recent_conversions: int
    traffic_ratio: float | None = None
    recent_conversion_rate: float | None = None
    active_experiments: int
    paused_experiments: int
    ingest_rejections: int
    cloudflare_sync_failures: int
    thresholds: MonitoringThresholds
    alerts: list[MonitoringAlert] = Field(default_factory=list)


class MultivariateFactorOption(ORMModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9-_]+$")
    label: str = Field(min_length=1, max_length=120)


class MultivariateFactor(ORMModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9-_]+$")
    label: str = Field(min_length=1, max_length=120)
    options: list[MultivariateFactorOption] = Field(min_length=2)


class MultivariatePreviewRequest(ORMModel):
    destination_url: HttpUrl
    factors: list[MultivariateFactor] = Field(min_length=2)
    hyros_tag_prefix: str | None = Field(default=None, max_length=120)


class MultivariatePreviewVariant(VariantBase):
    factor_assignments: dict[str, str] = Field(default_factory=dict)
