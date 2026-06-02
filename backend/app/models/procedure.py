"""程序主表模型（多版本模型，data-model §3.3）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    NullableTenantMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)


class Procedure(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
    """程序（SOP）。同一逻辑程序的多个版本共享 procedure_group_id。"""

    __tablename__ = "tb_procedure"

    # 版本族标识：同一逻辑程序的所有版本共享
    procedure_group_id: Mapped[str] = mapped_column(String(36), index=True)
    # 同 group 仅一条 is_current=TRUE（DB partial-unique 见迁移 current_guard）
    is_current: Mapped[bool] = mapped_column(default=True, server_default="1", index=True)
    folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_folder.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    version_change_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    # DRAFT / PUBLISHED / ARCHIVED（三态干净版）
    status: Mapped[str] = mapped_column(
        String(20), default="DRAFT", server_default="DRAFT", index=True
    )
    is_read: Mapped[bool] = mapped_column(default=False, server_default="0")
    read_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    custom_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 导入时刻的解析 warnings 快照（A 项）：[{stage, message, severity}]。
    # blocking=已放行的潜在丢失；info=有意裁剪/已知丢弃。编辑器常驻提示区据此渲染。
    import_notes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    risk_level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    quality_level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # 用途级别（Q182）：reference / continuous / information，无默认，创建必选
    level_of_use: Mapped[str] = mapped_column(String(20))
    # 乐观锁版本字段（与 version 不同，Q18）
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    version_update_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    deprecated_from_folder_id: Mapped[str | None] = mapped_column(String(36), default=None)
    deprecated_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    deprecated_by: Mapped[str | None] = mapped_column(String(128), default=None)
    archived_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    # PDF 操作员签字栏总开关（程序级，受控文档属性）
    signoff_enabled: Mapped[bool] = mapped_column(default=False, server_default="0")

    # 附件通过多态 Attachment（entity_type='procedure', entity_id=self.id）关联，无 ORM relationship。
