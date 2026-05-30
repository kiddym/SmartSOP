"""程序附件模型（data-model §3.6）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    NullableTenantMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)

if TYPE_CHECKING:
    from app.models.procedure import Procedure


class ProcedureAttachment(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
    """程序附件（挂在版本；upgrade/rollback/copy 复制元数据，storage_path 复用）。"""

    __tablename__ = "tb_procedure_attachment"

    procedure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="RESTRICT")
    )
    file_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    procedure: Mapped[Procedure] = relationship(back_populates="attachments")

    __table_args__ = (
        Index("ix_tb_procedure_attachment_procedure_id", "procedure_id"),
        Index("ix_tb_procedure_attachment_storage_path", "storage_path"),
    )
