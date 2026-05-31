"""多备件套件（MultiParts，每租户）。纯分组，无自身库存、无消耗行为。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class MultiPart(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_multi_part"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class MultiPartItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_multi_part_item"
    __table_args__ = (
        UniqueConstraint("multi_part_id", "part_id", name="uq_multi_part_item"),
    )

    multi_part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_multi_part.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
