"""工时分类（每租户）。镜像 CostCategory，带默认小时费率。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class TimeCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_time_category"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_time_category_company_name"),)

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
