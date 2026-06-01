"""邮件投递队列（Phase 5B）：append-only。tick 扫 pending 投递。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class EmailOutbox(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_email_outbox"
    __table_args__ = (
        Index("ix_email_outbox_status", "company_id", "status"),
    )

    recipient_user_id: Mapped[str] = mapped_column(String(36), index=True)
    recipient_email: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    sent_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    notification_id: Mapped[str | None] = mapped_column(String(36), default=None)
