"""资产停机时段（手动登记；无树传播，Phase 4 再做）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class AssetDowntime(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_asset_downtime"

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    downtime_type: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual"
    )
