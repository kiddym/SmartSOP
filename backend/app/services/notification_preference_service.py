"""邮件通知偏好服务（Phase 5B）。黑名单语义；未建记录=全默认开。

所有查询显式按 company_id 过滤（不依赖租户事件），以便调度上下文下亦正确。
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference

_DEFAULT = {"email_enabled": True, "disabled_types": []}


def _row(db: Session, company_id: str, user_id: str) -> NotificationPreference | None:
    return db.execute(
        select(NotificationPreference).where(
            NotificationPreference.company_id == company_id,
            NotificationPreference.user_id == user_id,
        )
    ).scalar_one_or_none()


def get(db: Session, company_id: str, user_id: str) -> dict:
    """返回偏好 dict；无记录返回默认（全开）。"""
    row = _row(db, company_id, user_id)
    if row is None:
        return dict(_DEFAULT)
    return {"email_enabled": row.email_enabled,
            "disabled_types": json.loads(row.disabled_types or "[]")}


def upsert(db: Session, company_id: str, user_id: str, *,
           email_enabled: bool, disabled_types: list[str]) -> NotificationPreference:
    """全量替换偏好（不 commit，由调用方提交）。"""
    row = _row(db, company_id, user_id)
    payload = json.dumps(list(dict.fromkeys(disabled_types)), ensure_ascii=False)
    if row is None:
        row = NotificationPreference(
            company_id=company_id, user_id=user_id,
            email_enabled=email_enabled, disabled_types=payload)
        db.add(row)
    else:
        row.email_enabled = email_enabled
        row.disabled_types = payload
    return row


def should_email(db: Session, company_id: str, user_id: str, type_: str) -> bool:
    """该用户该类型是否应收邮件 = 全局总闸 AND type 不在黑名单。"""
    pref = get(db, company_id, user_id)
    if not pref["email_enabled"]:
        return False
    return type_ not in pref["disabled_types"]
