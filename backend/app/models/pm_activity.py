"""PM 活动时间线（只增不软删，审计性质）。PM 无状态机，故无 from/to_status。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class PMActivity(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_pm_activity"

    pm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_preventive_maintenance.id", ondelete="CASCADE"), index=True
    )
    # CREATED / UPDATED / ENABLED / DISABLED / WO_GENERATED / COMMENT
    activity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    comment: Mapped[str] = mapped_column(Text, default="", server_default="")
