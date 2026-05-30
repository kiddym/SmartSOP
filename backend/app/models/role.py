"""Role: tenant-scoped role holding a list of permission codes."""
from __future__ import annotations

from sqlalchemy import String, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Role(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_role"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_role_company_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
