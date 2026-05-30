"""工单活动时间线（只增不软删，审计性质）。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class WorkOrderActivity(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_activity"

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    # STATUS_CHANGE / COMMENT / ASSIGN / SOP_ATTACH / STEP_DONE
    activity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    from_status: Mapped[str | None] = mapped_column(String(20), default=None)
    to_status: Mapped[str | None] = mapped_column(String(20), default=None)
    comment: Mapped[str] = mapped_column(Text, default="", server_default="")
