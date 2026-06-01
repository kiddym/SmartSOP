"""批量导入 API schema（snake_case，对齐既有 API 约定）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
    review_revision: int  # 暂存改判乐观锁当前版本（前端 PATCH review 携带）
    error: str | None


class BatchApplyRequest(BaseModel):
    item_ids: list[str] | None = None  # None = 该批次全部 review 项
    high_confidence_only: bool = False


class BatchApplyResult(BaseModel):
    enqueued: int


class ApplyPreviewOut(BaseModel):
    to_create: int  # 将新建程序数
    duplicate_skip: int  # content_hash 命中已落库 → 跳过
    target_folder_id: str


class ReviewOp(BaseModel):
    node_id: str
    action: Literal["accept", "to_content", "to_chapter", "set_level"]
    level: int | None = None  # set_level 时必填


class ReviewPatchRequest(BaseModel):
    review_revision: int
    ops: list[ReviewOp] = Field(min_length=1)


class ReviewPatchResult(BaseModel):
    review_revision: int
