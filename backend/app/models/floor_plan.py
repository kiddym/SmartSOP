"""位置平面图（每位置 1:N 平面图，每租户）。

一个位置可挂多张平面图，记录名称、图片地址与面积（m²）。
随位置 CASCADE 删除。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class FloorPlan(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_floor_plan"

    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(512), default=None)
    area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
