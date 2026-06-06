"""邮箱验证 token（净室原创，仿密码重置）。token 只存哈希、单次、限时。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class VerificationToken(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_verification_token"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DATETIME6)
    used_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
