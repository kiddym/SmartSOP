"""邮件 outbox 入队 + 投递（Phase 5B）。

enqueue：在 notify() 内部按偏好为每个有邮箱的活跃收件人写一条 pending 行
（同事务，不 commit）。渲染在入队时完成并落库（subject/body 快照）。
所有查询显式按 company_id 过滤。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.email.templates import render
from app.models.email_outbox import EmailOutbox
from app.models.user import User, UserStatus
from app.services import notification_preference_service as pref


def enqueue(
    db: Session,
    *,
    company_id: str,
    recipient_ids: set[str],
    type: str,
    params: dict,
    notification_id: str | None = None,
) -> int:
    """为应收邮件的收件人写 pending outbox 行。返回入队数。不 commit。"""
    if not recipient_ids:
        return 0
    rows = db.execute(
        select(User.id, User.email).where(
            User.company_id == company_id,
            User.id.in_(recipient_ids),
            User.status == UserStatus.active,
        )
    ).all()
    subject, body = render(type, params)
    count = 0
    for uid, email in rows:
        if not email:
            continue
        if not pref.should_email(db, company_id, uid, type):
            continue
        db.add(
            EmailOutbox(
                company_id=company_id,
                recipient_user_id=uid,
                recipient_email=email,
                type=type,
                subject=subject,
                body=body,
                status="pending",
                notification_id=notification_id,
            )
        )
        count += 1
    return count


def deliver_pending(db: Session, *, backend, max_attempts: int,
                    company_id: str) -> dict[str, int]:
    """投递某租户 pending 行（不 commit；由 tick 统一 commit）。"""
    from app.models.base import utcnow
    rows = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.company_id == company_id,
            EmailOutbox.status == "pending",
            EmailOutbox.attempts < max_attempts,
        )
    ).scalars().all()
    sent = failed = 0
    for row in rows:
        try:
            backend.send(row.recipient_email, row.subject, row.body,
                         from_addr=_from_addr())
            row.status = "sent"
            row.sent_at = utcnow()
            sent += 1
        except Exception as e:
            row.attempts += 1
            row.last_error = str(e)
            if row.attempts >= max_attempts:
                row.status = "failed"
            failed += 1
    return {"sent": sent, "failed_attempt": failed}


def _from_addr() -> str:
    from app.config import settings
    return settings.email_from
