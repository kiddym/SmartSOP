"""维修请求（每租户）。

work_order_id 为弱引用（无 FK）：审批后生成的工单属另一聚合，生成后各自演进。
priority 复用 WorkOrderPriority 枚举（DRY，同 NONE/LOW/MEDIUM/HIGH）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)
from app.models.request_status import RequestStatus
from app.models.work_order_status import WorkOrderPriority


class Request(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_request"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
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
    status: Mapped[RequestStatus] = mapped_column(
        SAEnum(RequestStatus), nullable=False, default=RequestStatus.PENDING
    )
    # 审批结果（弱引用，无 FK）
    work_order_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    resolution_note: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    resolved_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    # 业务自定义字段值（按 CustomFieldDef.key 存；JSON 括号表达式默认避开 MySQL 1101）
    custom_values: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("('{}')")
    )
