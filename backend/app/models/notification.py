"""站内通知模型（Phase 5A）：通知行 + 边沿状态行。append-only，无软删。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Notification(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """单收件人一行；广播事件=每收件人一行。结构化 params 存 JSON 字符串。"""

    __tablename__ = "tb_notification"
    __table_args__ = (
        Index("ix_tb_notification_recipient_read", "company_id", "recipient_user_id", "is_read"),
        Index("ix_tb_notification_dedup", "company_id", "dedup_key"),
    )

    recipient_user_id: Mapped[str] = mapped_column(String(36), index=True)
    type: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str | None] = mapped_column(String(40), default=None)
    entity_id: Mapped[str | None] = mapped_column(String(36), default=None)
    params: Mapped[str] = mapped_column(Text, default="{}", server_default=text("('{}')"))
    actor_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    read_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    dedup_key: Mapped[str | None] = mapped_column(String(120), default=None)


class NotificationArm(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """边沿状态：记录当前"已武装"的轮询条件（仿 meter is_armed）。"""

    __tablename__ = "tb_notification_arm"
    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_notification_arm"),)

    key: Mapped[str] = mapped_column(String(120))
