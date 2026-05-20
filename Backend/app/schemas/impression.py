from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import DeviceType, ORMModel, TrafficSource


class ImpressionEventIn(ORMModel):
    experiment_id: str
    variant_id: str
    device_type: DeviceType | None = None
    traffic_source: TrafficSource | None = None
    country: str | None = Field(default=None, max_length=8)
    ts: datetime | None = None


class ImpressionBatchIn(ORMModel):
    events: list[ImpressionEventIn] = Field(min_length=1)


class ImpressionBatchResult(ORMModel):
    inserted: int


class ConversionEventIn(ORMModel):
    experiment_id: str
    variant_id: str
    conversion_type: str = Field(min_length=1, max_length=120)
    visitor_id: str | None = Field(default=None, max_length=255)
    ts: datetime | None = None


class ConversionBatchIn(ORMModel):
    events: list[ConversionEventIn] = Field(min_length=1)


class ConversionBatchResult(ORMModel):
    inserted: int
