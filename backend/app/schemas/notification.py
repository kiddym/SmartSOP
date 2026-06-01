"""站内通知响应 schema（Phase 5A）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: str
    type: str
    entity_type: str | None
    entity_id: str | None
    params: dict[str, Any]
    actor_user_id: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class UnreadCount(BaseModel):
    count: int


class ReadAllResult(BaseModel):
    updated: int
