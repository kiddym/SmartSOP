"""批量导入作业与条目（批量解析 Word MVP — 后端地基）。

两阶段流水线的 parse-stage 状态载体：BatchImportJob 是一次批量上传，
BatchImportItem 是其中一份 docx。company_id 由 NullableTenantMixin 提供，
隔离交给全局 ORM 事件（app/tenant_isolation.py）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    DATETIME6,
    Base,
    NullableTenantMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)


class BatchImportJob(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
    """一次批量导入（N 份 docx）。status 由 items 聚合冗余，便于列表与轮询。"""

    __tablename__ = "tb_batch_import_job"

    folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_folder.id", ondelete="RESTRICT"), index=True
    )
    parse_mode: Mapped[str] = mapped_column(String(20), default="smart", server_default="smart")
    status: Mapped[str] = mapped_column(
        String(20), default="parsing", server_default="parsing", index=True
    )
    counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)

    items: Mapped[list[BatchImportItem]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class BatchImportItem(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
    """批次内一份 docx 的解析/审阅/落库生命周期。"""

    __tablename__ = "tb_batch_import_item"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_batch_import_job.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), default="", server_default="", index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="queued", server_default="queued", index=True
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parse_blob_ref: Mapped[str] = mapped_column(String(255), default="", server_default="")
    docx_ref: Mapped[str] = mapped_column(String(255), default="", server_default="")
    review_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_procedure_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="SET NULL"), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    leased_until: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)

    job: Mapped[BatchImportJob] = relationship(back_populates="items")
