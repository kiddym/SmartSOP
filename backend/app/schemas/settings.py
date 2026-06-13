"""全局设置 schema（api-specification §5.8）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SettingsOut(BaseModel):
    """GET /api/v1/settings 响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    enable_version_control: bool
    enable_approval_workflow: bool
    max_version_number: int
    require_read_confirmation: bool
    default_risk_level: int
    default_quality_level: int
    auto_archive_days: int
    revision: int
    updated_at: datetime


class SettingsUpdate(BaseModel):
    """PUT /api/v1/settings 请求体（可改字段）。

    enable_version_control 和 auto_archive_days 由后端忽略，不在此定义。
    """

    enable_approval_workflow: bool
    max_version_number: int = Field(ge=1, le=9999)
    require_read_confirmation: bool
    default_risk_level: int = Field(ge=1, le=5)
    default_quality_level: int = Field(ge=1, le=5)
