"""仪表读数（每租户，append-only 不软删，审计性质）。

value 用 Numeric(18,4) 避免浮点漂移影响阈值比较。reading_at 默认当前时刻。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
    utcnow,
)


class MeterReading(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_meter_reading"

    meter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_meter.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reading_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, default=utcnow)
    recorded_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
