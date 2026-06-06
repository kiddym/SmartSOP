"""资产折旧（每资产 1:1 的折旧信息）。

直线法折旧的原始参数存库，当前价值在 service/schema 计算（只读 computed）。
表名 tb_asset_deprecation；asset_id 唯一（1:1），随资产 CASCADE 删除。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class AssetDeprecation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_asset_deprecation"

    asset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tb_asset.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), default=None)
    purchase_date: Mapped[date | None] = mapped_column(Date, default=None)
    residual_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), default=None)
    useful_life_years: Mapped[int | None] = mapped_column(Integer, default=None)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), default=None)
