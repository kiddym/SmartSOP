"""工单分类 CRUD schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkOrderCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""


class WorkOrderCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None


class WorkOrderCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
