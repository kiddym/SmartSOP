"""客户（Customer，每租户）+ M:N 关联备件/资产/位置。billing_currency 为裸货币码（Currency 实体延后）。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Customer(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_customer"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(120), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    billing_currency: Mapped[str] = mapped_column(String(8), default="", server_default="")
    # 账单信息细化（全可空；与 billing_currency 同组）
    billing_name: Mapped[str | None] = mapped_column(String(300), default=None)
    billing_address: Mapped[str | None] = mapped_column(String(500), default=None)
    billing_address2: Mapped[str | None] = mapped_column(String(500), default=None)
    address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(60), default="", server_default="")
    email: Mapped[str] = mapped_column(String(200), default="", server_default="")
    website: Mapped[str] = mapped_column(String(300), default="", server_default="")


class CustomerPart(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_customer_part"
    __table_args__ = (UniqueConstraint("customer_id", "part_id", name="uq_customer_part"),)

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_customer.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )


class CustomerAsset(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_customer_asset"
    __table_args__ = (UniqueConstraint("customer_id", "asset_id", name="uq_customer_asset"),)

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_customer.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )


class CustomerLocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_customer_location"
    __table_args__ = (UniqueConstraint("customer_id", "location_id", name="uq_customer_location"),)

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_customer.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
