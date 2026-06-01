"""通用每租户自增序列（custom_id 生成）。

按 (company_id, scope) 维护一个计数器；scope 如 "asset"/"location"，
后续阶段（库存/采购/工单）可复用，仅新增 scope。
"""

from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class Sequence(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_sequence"
    __table_args__ = (UniqueConstraint("company_id", "scope", name="uq_sequence_company_scope"),)

    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    # 下一个待分配的编号（从 1 起）
    next_val: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
