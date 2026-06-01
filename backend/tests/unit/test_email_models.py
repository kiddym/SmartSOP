"""Phase 5B 邮件模型：偏好 + 投递 outbox。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.email_outbox import EmailOutbox
from app.models.notification_preference import NotificationPreference


def test_preference_defaults(db: Session):
    p = NotificationPreference(company_id="co-1", user_id="u-1")
    db.add(p)
    db.commit()
    db.refresh(p)
    assert p.email_enabled is True
    assert p.disabled_types == "[]"


def test_outbox_defaults(db: Session):
    o = EmailOutbox(
        company_id="co-1",
        recipient_user_id="u-1",
        recipient_email="a@x.com",
        type="WO_ASSIGNED",
        subject="s",
        body="b",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    assert o.status == "pending"
    assert o.attempts == 0
    assert o.sent_at is None
    rows = db.execute(select(EmailOutbox)).scalars().all()
    assert len(rows) == 1
