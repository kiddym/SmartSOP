"""工单额外成本（每租户）。cost_category_id 复用现有 CostCategory（可空）。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class WorkOrderAdditionalCost(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_additional_cost"

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    cost_category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_cost_category.id", ondelete="RESTRICT"), default=None
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
