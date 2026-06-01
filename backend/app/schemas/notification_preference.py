"""偏好读写 schema（Phase 5B）。"""

from __future__ import annotations

from pydantic import BaseModel


class NotificationPreferenceRead(BaseModel):
    email_enabled: bool
    disabled_types: list[str]


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool
    disabled_types: list[str]
