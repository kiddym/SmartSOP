"""工单工时（每租户）。计时器（started/stopped）与手填（duration_seconds）二合一。

成本计算唯一依据为 duration_seconds；运行中（stopped_at 为空）行 duration 为 0、
不入账，stop 时才落定。hourly_rate 为创建时快照，不随 TimeCategory 改动而变。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class WorkOrderLabor(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_labor"

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), default=None, index=True
    )
    time_category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_time_category.id", ondelete="RESTRICT"), default=None
    )
    started_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    stopped_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    # 是否计入工单总成本汇总（False 时该行从 labor 小计排除）
    include_to_total: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
