"""偏好服务：黑名单语义、未建记录默认全开、全量替换。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import notification_preference_service as svc

CO = "co-1"


def test_should_email_default_when_no_record(db: Session):
    assert svc.should_email(db, CO, "u-1", "WO_ASSIGNED") is True


def test_upsert_then_get(db: Session):
    svc.upsert(db, CO, "u-1", email_enabled=True, disabled_types=["WO_STATUS_CHANGED"])
    db.commit()
    pref = svc.get(db, CO, "u-1")
    assert pref["email_enabled"] is True
    assert pref["disabled_types"] == ["WO_STATUS_CHANGED"]


def test_should_email_respects_disabled_type(db: Session):
    svc.upsert(db, CO, "u-1", email_enabled=True, disabled_types=["WO_STATUS_CHANGED"])
    db.commit()
    assert svc.should_email(db, CO, "u-1", "WO_STATUS_CHANGED") is False
    assert svc.should_email(db, CO, "u-1", "WO_ASSIGNED") is True


def test_should_email_respects_master_switch(db: Session):
    svc.upsert(db, CO, "u-1", email_enabled=False, disabled_types=[])
    db.commit()
    assert svc.should_email(db, CO, "u-1", "WO_ASSIGNED") is False


def test_upsert_is_idempotent_replace(db: Session):
    svc.upsert(db, CO, "u-1", email_enabled=True, disabled_types=["A"])
    db.commit()
    svc.upsert(db, CO, "u-1", email_enabled=False, disabled_types=["B", "C"])
    db.commit()
    pref = svc.get(db, CO, "u-1")
    assert pref["email_enabled"] is False
    assert sorted(pref["disabled_types"]) == ["B", "C"]
