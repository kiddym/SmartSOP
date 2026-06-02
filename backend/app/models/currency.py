"""全局币种表（不挂租户，super_admin 维护，所有租户共读）。"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Currency(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tb_currency"

    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(8), default="", server_default="")
