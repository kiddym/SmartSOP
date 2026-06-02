"""公司级配置（每 company 一行 singleton）。"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class CompanySettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_company_settings"

    date_format: Mapped[str] = mapped_column(
        String(32), default="YYYY-MM-DD", server_default="YYYY-MM-DD"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Shanghai", server_default="Asia/Shanghai"
    )
    default_currency_code: Mapped[str] = mapped_column(
        String(8), default="CNY", server_default="CNY"
    )
    auto_assign: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
