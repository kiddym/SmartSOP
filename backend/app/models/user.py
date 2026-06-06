"""User: tenant-scoped account. Email unique within a company."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class UserStatus(enum.StrEnum):
    active = "active"
    disabled = "disabled"


class User(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_user"
    __table_args__ = (UniqueConstraint("company_id", "email", name="uq_user_company_email"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus), nullable=False, default=UserStatus.active
    )
    role_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_role.id", ondelete="SET NULL"), nullable=True
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    # Profile fields (optional). ``rate`` is the worker's default hourly labor
    # rate, used as a fallback when logging work-order labor.
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    job_title: Mapped[str | None] = mapped_column(String(128), default=None)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(512), default=None)
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    # Reserved: platform-operator identity (Phase 0: always False).
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 邮箱验证标记（附加能力，不作登录门槛；既有行迁移回填 True）。
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
