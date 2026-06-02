"""采购单（PO，每租户）：头 + 明细行 + 活动时间线。

头引用 Vendor（必填），行引用 Part（采购数量 + 单价快照）。
审批=整单入库回写 Part.quantity（见 purchase_order_service.approve）。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
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
from app.models.purchase_order_status import PurchaseOrderStatus


class PurchaseOrder(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_purchase_order"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    vendor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tb_vendor.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        SAEnum(PurchaseOrderStatus), nullable=False, default=PurchaseOrderStatus.DRAFT
    )
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_purchase_order_category.id", ondelete="SET NULL"), index=True
    )
    # 扩展元数据（非货币）：收货地址/方式/付款条款/预计交货日期
    shipping_address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    shipping_method: Mapped[str] = mapped_column(String(120), default="", server_default="")
    terms_of_payment: Mapped[str] = mapped_column(String(200), default="", server_default="")
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, default=None)
    resolution_note: Mapped[str] = mapped_column(Text, default="", server_default="")
    resolved_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)


class PurchaseOrderLine(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_purchase_order_line"

    purchase_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_purchase_order.id", ondelete="CASCADE"), index=True
    )
    # 行序（0-based 录入顺序）：明细按此稳定排序，避免按随机 UUID id 排序。
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )


class PurchaseOrderActivity(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_purchase_order_activity"

    purchase_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_purchase_order.id", ondelete="CASCADE"), index=True
    )
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    from_status: Mapped[str | None] = mapped_column(String(40), default=None)
    to_status: Mapped[str | None] = mapped_column(String(40), default=None)
    comment: Mapped[str] = mapped_column(Text, default="", server_default="")
