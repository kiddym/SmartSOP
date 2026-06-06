"""备件（Part，每租户）+ M:N 关联（指派人/团队/资产）。

cost/quantity/min_quantity 用 Numeric(18,4) 避免浮点漂移。is_low_stock 为计算
属性（非列）：计库存且 quantity<min_quantity。non_stock 备件永不低库存。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Part(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_part"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    min_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    unit: Mapped[str] = mapped_column(String(50), default="", server_default="")
    barcode: Mapped[str | None] = mapped_column(String(120), default=None)
    non_stock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_part_category.id", ondelete="SET NULL"), index=True
    )
    area: Mapped[str | None] = mapped_column(String(200), default=None)
    additional_infos: Mapped[str | None] = mapped_column(Text, default=None)

    @property
    def is_low_stock(self) -> bool:
        return (not self.non_stock) and (self.quantity < self.min_quantity)


class PartAssignee(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_assignee"
    __table_args__ = (UniqueConstraint("part_id", "user_id", name="uq_part_assignee"),)

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class PartTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_team"
    __table_args__ = (UniqueConstraint("part_id", "team_id", name="uq_part_team"),)

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )


class PartAsset(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_asset"
    __table_args__ = (UniqueConstraint("part_id", "asset_id", name="uq_part_asset"),)

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )


class PartLocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_location"
    __table_args__ = (UniqueConstraint("part_id", "location_id", name="uq_part_location"),)

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )


class PartPM(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_pm"
    __table_args__ = (UniqueConstraint("part_id", "pm_id", name="uq_part_pm"),)

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    pm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_preventive_maintenance.id", ondelete="CASCADE"), index=True
    )
