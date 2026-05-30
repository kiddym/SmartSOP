"""Company: the tenant root. Not tenant-scoped — its id IS the tenant id."""
from __future__ import annotations

import enum

from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class CompanyStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class Company(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tb_company"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[CompanyStatus] = mapped_column(
        SAEnum(CompanyStatus), nullable=False, default=CompanyStatus.active
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    # Reserved: platform-operator org (Phase 0: always False, no UI).
    is_platform_admin_org: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Reserved billing placeholders (Phase 6) — no logic attached.
    plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
