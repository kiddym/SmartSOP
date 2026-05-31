"""动态标题字典-编号体例 schema（方案 M4b）。字段 snake_case（Q350）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NumberingProfileOut(BaseModel):
    id: str
    pattern_key: str
    kind: str
    level: int | None
    source: str
    status: str
    level_votes: dict[str, Any] = Field(default_factory=dict)
    evidence_count: int
    agreement: float
    revision: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NumberingProfileCreate(BaseModel):
    pattern_key: str = Field(min_length=1, max_length=64)
    kind: str = "heading"  # heading | weak_heading | list
    level: int | None = Field(default=None, ge=0, le=9)


class NumberingProfileUpdate(BaseModel):
    kind: str | None = None
    level: int | None = Field(default=None, ge=0, le=9)
    status: str | None = None
