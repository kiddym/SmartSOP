"""备件消耗台账（每租户，append-only 不软删，审计性质）。

挂工单消耗：扣库存（non_stock 除外）并定格 unit_cost 单价快照。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
    utcnow,
)


class PartConsumption(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_consumption"

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="RESTRICT"), index=True
    )
    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    consumed_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    consumed_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, default=utcnow)
