"""用户邀请（净室原创实现）。token 只存哈希。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class UserInvitation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_user_invitation"

    email: Mapped[str] = mapped_column(String(255), index=True)
    role_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_role.id", ondelete="SET NULL"), default=None
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DATETIME6)
    # pending | accepted | revoked
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    invited_by: Mapped[str | None] = mapped_column(String(36), default=None)
