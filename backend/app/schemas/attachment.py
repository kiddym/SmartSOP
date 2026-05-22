"""附件 schema（api-specification §5.5 / data-model §3.6 / Q113-Q120 / Q371）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AttachmentOut(BaseModel):
    """附件元数据（GET /procedures/{id}/attachments 行 / 上传响应）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    procedure_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    description: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class AttachmentUpdate(BaseModel):
    """修改附件元数据（PUT /attachments/{id}，仅 description / sort_order，Q116）。"""

    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0)
