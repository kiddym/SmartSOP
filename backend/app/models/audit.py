"""审计日志模型（data-model §3.9）。

追加表：BIGINT 自增主键，只记 created_at，不软删、不更新。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, utcnow

# 审计 PK：MySQL 用 BIGINT 自增；SQLite 须为 INTEGER 才能复用 rowid 自增。
_AUDIT_PK = BigInteger().with_variant(Integer, "sqlite")


class _AuditLogColumns:
    """两张审计表共享列。"""

    id: Mapped[int] = mapped_column(_AUDIT_PK, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(30))
    old_value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    new_value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    ip_address: Mapped[str] = mapped_column(String(45), default="", server_default="")
    user_agent: Mapped[str] = mapped_column(String(500), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DATETIME6, default=utcnow)


class FolderAuditLog(_AuditLogColumns, Base, TenantMixin):
    """文件夹审计日志。"""

    __tablename__ = "tb_folder_audit_log"

    __table_args__ = (
        Index("ix_tb_folder_audit_log_target_id_created_at", "target_id", "created_at"),
        Index("ix_tb_folder_audit_log_action_created_at", "action", "created_at"),
        Index("ix_tb_folder_audit_log_created_at", "created_at"),
    )


class ProcedureAuditLog(_AuditLogColumns, Base, TenantMixin):
    """程序审计日志。冗存 procedure_group_id 便于查整族历史（Q127）。"""

    __tablename__ = "tb_procedure_audit_log"

    procedure_group_id: Mapped[str | None] = mapped_column(String(36), index=True)

    __table_args__ = (
        Index("ix_tb_procedure_audit_log_target_id_created_at", "target_id", "created_at"),
        Index(
            "ix_tb_procedure_audit_log_group_id_created_at",
            "procedure_group_id",
            "created_at",
        ),
        Index("ix_tb_procedure_audit_log_action_created_at", "action", "created_at"),
        Index("ix_tb_procedure_audit_log_created_at", "created_at"),
    )
