"""供应商（Vendor，每租户）+ M:N 关联备件/资产/位置。纯主数据，无编号、无库存行为。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Vendor(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_vendor"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    vendor_type: Mapped[str] = mapped_column(String(120), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(60), default="", server_default="")
    email: Mapped[str] = mapped_column(String(200), default="", server_default="")
    website: Mapped[str] = mapped_column(String(300), default="", server_default="")


class VendorPart(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_vendor_part"
    __table_args__ = (UniqueConstraint("vendor_id", "part_id", name="uq_vendor_part"),)

    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_vendor.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )


class VendorAsset(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_vendor_asset"
    __table_args__ = (UniqueConstraint("vendor_id", "asset_id", name="uq_vendor_asset"),)

    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_vendor.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )


class VendorLocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_vendor_location"
    __table_args__ = (UniqueConstraint("vendor_id", "location_id", name="uq_vendor_location"),)

    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_vendor.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
