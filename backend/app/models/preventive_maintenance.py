"""预防性维护（PM，每租户）。

按时间 interval 自动生成工单：调度任务扫到 next_due_date<=today 且启用的 PM →
复制预设生成工单 → 锥摆推进 next_due_date。priority 复用 WorkOrderPriority。
asset/location FK RESTRICT 弱关联；primary_user FK SET NULL；procedure_id 无 FK 弱引用。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
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
from app.models.pm_frequency import PMFrequencyUnit
from app.models.work_order_status import WorkOrderPriority


class PreventiveMaintenance(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_preventive_maintenance"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    priority: Mapped[WorkOrderPriority] = mapped_column(
        SAEnum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.NONE
    )
    asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
    primary_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), index=True
    )
    procedure_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    frequency_unit: Mapped[PMFrequencyUnit] = mapped_column(SAEnum(PMFrequencyUnit), nullable=False)
    frequency_value: Mapped[int] = mapped_column(Integer, nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 生单时工单 due_date = 生成日 + due_date_delay 天（默认 0=当日；表达"给 N 天完成"）。
    due_date_delay: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # 排程结束日：next_due_date 超过 ends_on 时停止再生成并自动停用（None=永不结束）。
    ends_on: Mapped[date | None] = mapped_column(Date, default=None)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    last_generated_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    last_work_order_id: Mapped[str | None] = mapped_column(String(36), default=None)
    # 连续无人响应工单计数（失效自停近似信号）：达阈值自动 disabled，防僵尸刷单。
    consecutive_unresponded: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class PMAssignee(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_pm_assignee"
    __table_args__ = (UniqueConstraint("pm_id", "user_id", name="uq_pm_assignee"),)

    pm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_preventive_maintenance.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class PMTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_pm_team"
    __table_args__ = (UniqueConstraint("pm_id", "team_id", name="uq_pm_team"),)

    pm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_preventive_maintenance.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
