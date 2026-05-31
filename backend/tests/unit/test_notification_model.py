from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm


def test_notification_defaults(db: Session):
    n = Notification(
        company_id="co-1", recipient_user_id="u-1", type="WO_ASSIGNED",
        entity_type="work_order", entity_id="wo-1", params='{"custom_id": "WO1"}',
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    assert n.id and n.created_at is not None
    assert n.is_read is False and n.read_at is None
    assert n.actor_user_id is None and n.dedup_key is None


def test_notification_arm_unique(db: Session):
    db.add(NotificationArm(company_id="co-1", key="PART_LOW_STOCK:p-1"))
    db.commit()
    a = db.get(NotificationArm, db.query(NotificationArm).one().id)
    assert a.key == "PART_LOW_STOCK:p-1" and a.company_id == "co-1"
