"""动态标题字典-样式规则 schema（动态标题字典与自学习方案 M1）。

M1 端点为「管理员手动维护」：列表 / 创建 / 更新 / 删除。level=0 或 null 表示
「此样式非标题（按正文处理）」。字段 snake_case，对齐既有 API（Q350）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HeadingRuleOut(BaseModel):
    id: str
    style_name: str
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


class HeadingRuleCreate(BaseModel):
    style_name: str = Field(min_length=1, max_length=255)
    # 1/2/3 = 标题层级；0/null = 显式判定「非标题/正文」。
    level: int | None = Field(default=None, ge=0, le=9)


class HeadingRuleUpdate(BaseModel):
    level: int | None = Field(default=None, ge=0, le=9)
    # 'active'（解析时应用）| 'candidate'（暂不应用）| 'disabled'。
    status: str | None = None
