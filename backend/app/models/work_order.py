"""工单及其指派关联（每租户）。

procedure_id/procedure_group_id 为弱引用（无 FK）：钉定的 Procedure 版本
不可变且属 SOP 聚合，故不设外键约束（见 spec §3.1/§3.3）。
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

from app.models.base import DATETIME6, Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin
from app.models.work_order_status import WorkOrderPriority, WorkOrderRelationType, WorkOrderStatus


class WorkOrder(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_work_order"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
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
    # 完成归属与反馈（2B）
    completed_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    feedback: Mapped[str | None] = mapped_column(Text, default=None)
    # 紧急旗标（与 priority 正交）
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 估时（分钟）与预计开始日
    estimated_duration: Mapped[int | None] = mapped_column(Integer, default=None)
    estimated_start_date: Mapped[date | None] = mapped_column(Date, default=None)
    # 首次离开 OPEN 的时刻（MTTA 原料，只记一次）
    first_responded_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    # 归档维度（与 is_active 软删正交）
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 完成时自动判定的合规快照；未完成为 None
    is_compliant: Mapped[bool | None] = mapped_column(Boolean, default=None)
    # 完成签名：required_signature=True 时完成前必须存档 signature_url（否则 422）
    signature_url: Mapped[str | None] = mapped_column(String(512), default=None)
    required_signature: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )


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


class WorkOrderRelation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_relation"
    __table_args__ = (
        UniqueConstraint(
            "source_work_order_id",
            "target_work_order_id",
            "relation_type",
            name="uq_work_order_relation",
        ),
    )

    source_work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    target_work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[WorkOrderRelationType] = mapped_column(
        SAEnum(WorkOrderRelationType), nullable=False
    )
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
