"""投递 tick：pending→sent；失败累加 attempts；达上限→failed；跨租户。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.email.backends import MemoryBackend
from app.models.email_outbox import EmailOutbox
from app.tasks import email_dispatch

CO = "co-1"


def _pending(db, cid=CO, email="a@x.com"):
    o = EmailOutbox(
        company_id=cid,
        recipient_user_id="u-1",
        recipient_email=email,
        type="WO_ASSIGNED",
        subject="s",
        body="b",
        status="pending",
    )
    db.add(o)
    db.commit()
    return o


def test_delivers_pending_marks_sent(db: Session):
    _pending(db)
    backend = MemoryBackend()
    summary = email_dispatch.run(db, backend=backend)
    assert summary["sent"] == 1
    row = db.execute(select(EmailOutbox)).scalar_one()
    assert row.status == "sent"
    assert row.sent_at is not None
    assert backend.sent[0][0] == "a@x.com"


def test_failure_increments_attempts(db: Session):
    _pending(db)

    class _Boom:
        def send(self, *a, **k):
            raise RuntimeError("smtp down")

    summary = email_dispatch.run(db, backend=_Boom(), max_attempts=5)
    assert summary["failed_attempt"] == 1
    row = db.execute(select(EmailOutbox)).scalar_one()
    assert row.status == "pending"  # 未达上限，留待重试
    assert row.attempts == 1
    assert "smtp down" in row.last_error


def test_reaches_max_attempts_marks_failed(db: Session):
    o = _pending(db)
    o.attempts = 4
    db.commit()

    class _Boom:
        def send(self, *a, **k):
            raise RuntimeError("x")

    email_dispatch.run(db, backend=_Boom(), max_attempts=5)
    row = db.execute(select(EmailOutbox)).scalar_one()
    assert row.attempts == 5
    assert row.status == "failed"


def test_sent_rows_not_redelivered(db: Session):
    o = _pending(db)
    o.status = "sent"
    db.commit()
    backend = MemoryBackend()
    summary = email_dispatch.run(db, backend=backend)
    assert summary["sent"] == 0
    assert backend.sent == []
