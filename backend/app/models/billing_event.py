"""Stripe webhook 事件去重日志（Phase 6）。

非租户表：webhook 无认证、按 customer 解析公司，事件本身不属单租户。
event_id 为 Stripe 事件 id（主键）；命中即视为已处理，保证幂等。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, utcnow


class BillingEvent(Base):
    __tablename__ = "tb_billing_event"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, default=utcnow)
