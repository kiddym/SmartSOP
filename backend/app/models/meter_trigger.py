"""仪表工单触发器（WorkOrderMeterTrigger，每租户）。

comparator+threshold 定义阈值；is_armed 为边沿去重武装态；其余字段为生单预设
（复用 WorkOrderPriority）。priority/primary_user 弱关联，procedure_id 无 FK 弱引用。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)
from app.models.meter_comparator import MeterComparator
from app.models.work_order_status import WorkOrderPriority


class MeterTrigger(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_meter_trigger"

    meter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_meter.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    comparator: Mapped[MeterComparator] = mapped_column(SAEnum(MeterComparator), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    is_armed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    priority: Mapped[WorkOrderPriority] = mapped_column(
        SAEnum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.NONE
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    primary_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), index=True
    )
    procedure_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    last_work_order_id: Mapped[str | None] = mapped_column(String(36), default=None)


class MeterTriggerAssignee(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_meter_trigger_assignee"
    __table_args__ = (UniqueConstraint("trigger_id", "user_id", name="uq_meter_trigger_assignee"),)

    trigger_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_meter_trigger.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class MeterTriggerTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_meter_trigger_team"
    __table_args__ = (UniqueConstraint("trigger_id", "team_id", name="uq_meter_trigger_team"),)

    trigger_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_meter_trigger.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
