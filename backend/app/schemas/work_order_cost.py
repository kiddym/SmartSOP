"""工单工时成本 schema（TimeCategory / Labor / AdditionalCost / CostSummary）。"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TimeCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    hourly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    description: str = ""


class TimeCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    description: str | None = None


class TimeCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    hourly_rate: Decimal
    description: str
