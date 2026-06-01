"""批量导入 API schema（snake_case，对齐既有 API 约定）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BatchImportItemIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    upload_token: str = Field(min_length=1)


class BatchImportCreate(BaseModel):
    folder_id: str
    parse_mode: str = "smart"
    items: list[BatchImportItemIn] = Field(min_length=1)


class BatchImportJobOut(BaseModel):
    id: str
    folder_id: str
    parse_mode: str
    status: str
    counts: dict[str, int]
    created_at: datetime


class BatchImportItemOut(BaseModel):
    id: str
    job_id: str
    filename: str
    status: str
    content_hash: str
    summary: dict[str, Any]
    error: str | None
