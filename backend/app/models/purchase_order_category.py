"""采购单分类（每租户）。复刻通用分类模式：name + description，重名按 company 唯一。"""

from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class PurchaseOrderCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_purchase_order_category"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_purchase_order_category_company_name"),
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
