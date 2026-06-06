"""仪表（Meter，每租户）。挂资产；unit/update_frequency_days 为元数据。

读数命中触发器阈值→自动生成工单（见 meter_trigger）。
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Meter(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_meter"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="", server_default="")
    update_frequency_days: Mapped[int | None] = mapped_column(Integer, default=None)
    asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
    meter_category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_meter_category.id", ondelete="SET NULL"), index=True
    )
