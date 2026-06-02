"""资产停机时段：手动登记，或由状态跨 UP/DOWN 边界自动触发（auto/cascade）。

source_asset_id 指向级联触发的祖先资产（auto/手动记录为 None）；prior_status 记录级联
导致后代状态变更前的原状态，供恢复时还原。详见 maintenance_asset_service 的停机树传播。
"""

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
    source_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tb_asset.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    prior_status: Mapped[str | None] = mapped_column(String(20), default=None)
