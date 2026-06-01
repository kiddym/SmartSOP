"""notify() 内联 enqueue：按偏好生成 outbox，邮箱快照，无 User 行则跳过。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.email_outbox import EmailOutbox
from app.models.user import User, UserStatus
from app.services import notification_preference_service as pref
from app.services import notification_service as notif

CO = "co-1"


def _user(db, uid, email):
    db.add(
        User(
            id=uid,
            email=email,
            password_hash="x",
            name=uid,
            status=UserStatus.active,
            company_id=CO,
        )
    )
    db.commit()


def test_enqueue_for_user_with_email(db: Session):
    _user(db, "u-1", "u1@x.com")
    notif.notify(
        db,
        company_id=CO,
        recipient_ids={"u-1"},
        type="WO_ASSIGNED",
        entity_type="work_order",
        entity_id="wo-1",
        params={"custom_id": "WO1", "title": "t"},
        actor_user_id=None,
    )
    db.commit()
    rows = db.execute(select(EmailOutbox)).scalars().all()
    assert len(rows) == 1
    assert rows[0].recipient_email == "u1@x.com"
    assert rows[0].status == "pending"
    assert rows[0].subject  # 已渲染


def test_no_user_row_skips_enqueue(db: Session):
    notif.notify(
        db,
        company_id=CO,
        recipient_ids={"ghost"},
        type="WO_ASSIGNED",
        entity_type="work_order",
        entity_id="wo-1",
        params={"custom_id": "WO1"},
        actor_user_id=None,
    )
    db.commit()
    assert db.execute(select(EmailOutbox)).scalars().all() == []


def test_disabled_type_skips_enqueue(db: Session):
    _user(db, "u-1", "u1@x.com")
    pref.upsert(db, CO, "u-1", email_enabled=True, disabled_types=["WO_ASSIGNED"])
    db.commit()
    notif.notify(
        db,
        company_id=CO,
        recipient_ids={"u-1"},
        type="WO_ASSIGNED",
        entity_type="work_order",
        entity_id="wo-1",
        params={"custom_id": "WO1"},
        actor_user_id=None,
    )
    db.commit()
    assert db.execute(select(EmailOutbox)).scalars().all() == []


def test_master_switch_off_skips(db: Session):
    _user(db, "u-1", "u1@x.com")
    pref.upsert(db, CO, "u-1", email_enabled=False, disabled_types=[])
    db.commit()
    notif.notify(
        db,
        company_id=CO,
        recipient_ids={"u-1"},
        type="WO_ASSIGNED",
        entity_type="work_order",
        entity_id="wo-1",
        params={"custom_id": "WO1"},
        actor_user_id=None,
    )
    db.commit()
    assert db.execute(select(EmailOutbox)).scalars().all() == []
