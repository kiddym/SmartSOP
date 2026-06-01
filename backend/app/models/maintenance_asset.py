"""CMMS 设备资产（自引用树）+ 负责人/团队关联（每租户）。

注意：文件名为 maintenance_asset 以避开既有 app/models/asset.py（SOP
ProcedureAsset）。类名 Asset、表名 tb_asset。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.asset_status import AssetStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin


class Asset(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_asset"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset_category.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[AssetStatus] = mapped_column(
        SAEnum(AssetStatus), nullable=False, default=AssetStatus.OPERATIONAL
    )
    serial_number: Mapped[str] = mapped_column(String(200), default="", server_default="")
    model: Mapped[str] = mapped_column(String(200), default="", server_default="")
    manufacturer: Mapped[str] = mapped_column(String(200), default="", server_default="")
    power: Mapped[str] = mapped_column(String(100), default="", server_default="")
    warranty_expiration_date: Mapped[date | None] = mapped_column(Date, default=None)
    in_service_date: Mapped[date | None] = mapped_column(Date, default=None)
    acquisition_cost: Mapped[float | None] = mapped_column(Numeric(18, 2), default=None)
    barcode: Mapped[str | None] = mapped_column(String(120), default=None, index=True)
    nfc_id: Mapped[str | None] = mapped_column(String(120), default=None, index=True)
    primary_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), index=True
    )


class AssetUser(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_asset_user"
    __table_args__ = (UniqueConstraint("asset_id", "user_id", name="uq_asset_user"),)

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class AssetTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_asset_team"
    __table_args__ = (UniqueConstraint("asset_id", "team_id", name="uq_asset_team"),)

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
