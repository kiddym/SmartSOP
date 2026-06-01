"""ORM 基类、公共 Mixin 与可移植类型工具（Phase 1）。

设计要点：
- 主键统一 UUID v4 字符串（CHAR(36)），应用层生成（database-specification §4）。
- 时间戳存 naive UTC（DB 无时区），毫秒精度 DATETIME(6)。
- 业务表全部软删（is_active + deleted_at）；审计表例外，自行定义。
- 类型用 `.with_variant` 兼容 MySQL（生产）与 SQLite（测试）双方言。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, MetaData, String, Text
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME
from sqlalchemy.dialects.mysql import LONGTEXT as MYSQL_LONGTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 约束 / 索引命名规范（database-specification §2.3 / §2.4）。
# 显式命名的复合约束在各模型 / 迁移里手写，避免超 64 字符标识符上限。
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}

# 可移植列类型：生产走 MySQL 专用类型，测试在 SQLite 上回退到通用类型。
DATETIME6 = DateTime().with_variant(MYSQL_DATETIME(fsp=6), "mysql")
LONGTEXT = Text().with_variant(MYSQL_LONGTEXT(), "mysql")


def utcnow() -> datetime:
    """naive UTC 当前时间（用于 DB 写入，避免 datetime.utcnow 弃用警告）。"""
    return datetime.now(UTC).replace(tzinfo=None)


def new_uuid() -> str:
    """生成 UUID v4 字符串主键。"""
    return str(uuid4())


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDMixin:
    """UUID v4 字符串主键。"""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    """创建 / 更新时间戳（DATETIME(6)，naive UTC）。"""

    created_at: Mapped[datetime] = mapped_column(DATETIME6, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DATETIME6, default=utcnow, onupdate=utcnow)


class SoftDeleteMixin:
    """软删除标志。查询默认应过滤 is_active=True（见 services 层 helper）。"""

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)


class TenantScoped:
    """Marker base for any entity participating in tenant row-level scoping.

    The isolation events (do_orm_execute / before_flush) target this marker,
    so both NOT-NULL platform tables and nullable SOP tables are covered.
    """


class TenantMixin(TenantScoped):
    """Platform tables: company_id is required (NOT NULL)."""

    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tb_company.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class NullableTenantMixin(TenantScoped):
    """SOP tables (Phase 0): company_id nullable; enforcement deferred to Phase 1."""

    company_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tb_company.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
