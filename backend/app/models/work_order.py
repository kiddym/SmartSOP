"""工单及其指派关联（每租户）。

procedure_id/procedure_group_id 为弱引用（无 FK）：钉定的 Procedure 版本
不可变且属 SOP 聚合，故不设外键约束（见 spec §3.1/§3.3）。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus


class WorkOrder(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_work_order"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[WorkOrderStatus] = mapped_column(
        SAEnum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.OPEN
    )
    priority: Mapped[WorkOrderPriority] = mapped_column(
        SAEnum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.NONE
    )
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
    primary_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), index=True
    )
    # SOP 钉定（弱引用，无 FK）
    procedure_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    procedure_group_id: Mapped[str | None] = mapped_column(String(36), default=None)
    procedure_attached_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    # 来源请求（弱引用，无 FK；直建工单时为 None）
    request_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    # 工单分类（FK，删分类时置空）
    category_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tb_work_order_category.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    # 创建者 user id（仅记录，不建 FK）
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)


class WorkOrderAssignee(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_assignee"
    __table_args__ = (UniqueConstraint("work_order_id", "user_id", name="uq_work_order_assignee"),)

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class WorkOrderTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_team"
    __table_args__ = (UniqueConstraint("work_order_id", "team_id", name="uq_work_order_team"),)

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
