"""审计日志响应 schema（api-specification §5.9）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogItem(BaseModel):
    """单条文件夹审计日志。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: str
    action: str
    old_value: dict[str, Any] = Field(default_factory=dict)
    new_value: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    ip_address: str = ""
    user_agent: str = ""
    created_at: datetime


class ProcedureAuditLogItem(AuditLogItem):
    """单条程序审计日志（额外含 procedure_group_id）。"""

    procedure_group_id: str | None


class AuditLogPage(BaseModel):
    """文件夹审计日志分页响应。"""

    total: int
    page: int
    page_size: int
    items: list[AuditLogItem]


class ProcedureAuditLogPage(BaseModel):
    """程序审计日志分页响应。"""

    total: int
    page: int
    page_size: int
    items: list[ProcedureAuditLogItem]
