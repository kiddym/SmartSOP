"""计量分类 schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MeterCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class MeterCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class MeterCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None = None
