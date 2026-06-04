"""邮件通知偏好（Phase 5B）：全局总闸 + 被禁类型黑名单。每用户一行。"""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class NotificationPreference(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_notification_preference"
    __table_args__ = (UniqueConstraint("company_id", "user_id", name="uq_notif_pref_user"),)

    user_id: Mapped[str] = mapped_column(String(36), index=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # json 数组：被关掉的通知类型码（黑名单）。空 = 全开。
    disabled_types: Mapped[str] = mapped_column(Text, default="[]", server_default=text("('[]')"))
