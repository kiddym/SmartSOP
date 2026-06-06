"""位置平面图 schema。

平面图与位置 1:N。name 必填；image_url / area 可空。
area 为 Numeric(12,2)，序列化为 Decimal。
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FloorPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    image_url: str | None = Field(default=None, max_length=512)
    area: Decimal | None = None


class FloorPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    image_url: str | None = Field(default=None, max_length=512)
    area: Decimal | None = None


class FloorPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    location_id: str
    name: str
    image_url: str | None = None
    area: Decimal | None = None
