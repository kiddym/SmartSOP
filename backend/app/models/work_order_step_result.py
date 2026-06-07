"""工单执行行（版本钉定，仅 kind='step' 节点生成）。

node_id 为弱引用（无 FK）：钉定版本不可变且节点属 SOP 聚合。
node_code/node_sort_order 生成时冗余拷入，使执行视图自包含、排序稳定。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin


class WorkOrderStepResult(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_work_order_step_result"

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    node_code: Mapped[str] = mapped_column(String(50), default="", server_default="")
    node_sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_done: Mapped[bool] = mapped_column(default=False, server_default="0")
    done_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    done_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    notes: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))

    __table_args__ = (
        UniqueConstraint("work_order_id", "node_id", name="uq_work_order_step_result_node"),
    )
