"""移动端推送 token（净室原创）：每用户多设备 token，按 (user_id, token) 去重。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class PushToken(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_push_token"
    __table_args__ = (UniqueConstraint("user_id", "token", name="uq_push_token_user_token"),)

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(512))
    platform: Mapped[str] = mapped_column(String(16))  # 'ios' / 'android' / 'web'
