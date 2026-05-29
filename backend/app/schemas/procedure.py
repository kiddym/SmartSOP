"""程序相关 schema（api-specification §5.2 / data-model §3.3 / Q176/Q182/Q278）。

Phase 3 = 基础 CRUD + 多版本骨架。upgrade/rollback/deprecate/restore/copy 属 Phase 7。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentOut
from app.schemas.common import BatchDeleteFailure

LevelOfUse = Literal["reference", "continuous", "information"]
Status = Literal["DRAFT", "PUBLISHED", "ARCHIVED"]


class ProcedureCreate(BaseModel):
    """创建空白程序（POST /procedures）。code 由后端按 folder.prefix + 序号生成。"""

    folder_id: str
    name: str = Field(min_length=1, max_length=200)
    level_of_use: LevelOfUse  # Q182 必填，无默认
    description: str = Field(default="", max_length=10000)
    risk_level: int = Field(default=1, ge=1, le=5)
    quality_level: int = Field(default=1, ge=1, le=5)
    custom_values: dict[str, Any] = Field(default_factory=dict)


class ProcedureUpdate(BaseModel):
    """更新程序元数据（PUT /procedures/{id}，仅 is_current=true 且 DRAFT）。"""

    name: str = Field(min_length=1, max_length=200)
    level_of_use: LevelOfUse
    description: str = Field(default="", max_length=10000)
    risk_level: int = Field(default=1, ge=1, le=5)
    quality_level: int = Field(default=1, ge=1, le=5)
    custom_values: dict[str, Any] = Field(default_factory=dict)
    version_update_notes: str = Field(default="", max_length=10000)
    signoff_enabled: bool = Field(default=False)


class TransitionIn(BaseModel):
    """状态切换入参（POST /procedures/{id}/transition）。"""

    status: Status
    reason: str = Field(default="", max_length=2000)


# --------------------------------------------------------------------------- #
# 版本管理（Phase 7）
# --------------------------------------------------------------------------- #
class ReasonIn(BaseModel):
    """通用 reason 必填入参（deprecate 等）。"""

    reason: str = Field(min_length=1, max_length=2000)


class RollbackIn(BaseModel):
    """回退入参（POST /procedures/{id}/rollback）。"""

    target_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)


class RestoreIn(BaseModel):
    """恢复入参（POST /procedures/{id}/restore）；原文件夹已删时 target_folder_id 必填。"""

    reason: str = Field(min_length=1, max_length=2000)
    target_folder_id: str | None = None


class CopyIn(BaseModel):
    """复制为新程序入参（POST /procedures/{id}/copy）。"""

    target_folder_id: str
    name: str | None = Field(default=None, max_length=200)


class RestorePreviewOut(BaseModel):
    """恢复前预检查（§22.5）。"""

    folder_exists: bool
    deprecated_from_folder_id: str | None
    folder_full_path: str | None
    version_count: int


class DiscardDraftResult(BaseModel):
    """丢弃 DRAFT 特殊路径响应（§22.11）。"""

    deleted_id: str
    new_current_id: str
    new_current_version: int


class VersionListItem(BaseModel):
    """group 版本列表行（§22.2 / GET /procedure-groups/{group_id}/versions）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    status: str
    is_current: bool
    version_update_notes: str
    version_update_notes_preview: str
    created_at: datetime
    archived_at: datetime | None


class VersionListOut(BaseModel):
    """group 版本列表（count_only=true 时 items 为空仅返 count）。"""

    count: int
    items: list[VersionListItem] = Field(default_factory=list)


class ProcedureDeleteIn(BaseModel):
    """删除入参（reason 必填，Q128）。"""

    reason: str = Field(min_length=1, max_length=2000)


class ProcedureBatchDeleteIn(BaseModel):
    """批量软删（原子，≤100 项，Q20/Q325）。"""

    ids: list[str] = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=2000)


class BatchMoveIn(BaseModel):
    """批量移动到叶子文件夹（code 不变，Q22/Q273）。"""

    ids: list[str] = Field(min_length=1, max_length=100)
    target_folder_id: str


class BatchMoveResult(BaseModel):
    """批量移动结果：成功 ID + 错误详情（原子，任一失败全不动）。"""

    moved_ids: list[str]
    failed: list[BatchDeleteFailure]


class ProcedureOut(BaseModel):
    """程序库列表行（每 group 一行 is_current + derived 字段，Q176）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    procedure_group_id: str
    code: str
    name: str
    version: int
    is_current: bool
    status: str
    folder_id: str
    folder_full_path: str
    level_of_use: str
    risk_level: int
    quality_level: int
    description: str
    signoff_enabled: bool
    revision: int
    version_count_in_group: int
    created_at: datetime
    updated_at: datetime


class ProcedureMeta(BaseModel):
    """程序详情的 procedure 子对象（GET /procedures/{id}.procedure）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    procedure_group_id: str
    code: str
    name: str
    version: int
    is_current: bool
    status: str
    folder_id: str
    folder_full_path: str
    description: str
    risk_level: int
    quality_level: int
    level_of_use: str
    custom_values: dict[str, Any]
    version_update_notes: str
    signoff_enabled: bool
    revision: int
    is_read: bool
    read_at: datetime | None
    deprecated_from_folder_id: str | None
    deprecated_at: datetime | None
    archived_at: datetime | None
    version_change_log: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class FieldOut(BaseModel):
    """程序详情面板渲染用的 active 自定义字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    key: str
    field_type: str
    required: bool
    options: list[dict[str, Any]]
    sort_order: int
    show_on_cover: bool


class ProcedureDetail(BaseModel):
    """GET /procedures/{id} 一次拉全部（Q153）：元信息 + 附件 + 字段。"""

    procedure: ProcedureMeta
    attachments: list[AttachmentOut] = Field(default_factory=list)
    fields: list[FieldOut] = Field(default_factory=list)
    has_source_docx: bool = False  # 该 group 是否有原始 Word 源文件（前端据此决定是否拉预览）
