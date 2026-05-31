from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder
from app.services import notification_service as notif

CO = "co-1"


def test_on_wo_auto_generated_notifies_primary(db: Session):
    db.add(User(id="p1", email="p1@x.com", password_hash="x", name="p1",
                status=UserStatus.active, company_id=CO))
    db.commit()
    wo = WorkOrder(custom_id="WO9", title="自动单", primary_user_id="p1", company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    notif.on_wo_auto_generated(db, wo, actor_user_id=None)
    db.commit()
    row = db.execute(select(Notification)).scalars().one()
    assert row.type == "WO_AUTO_GENERATED" and row.recipient_user_id == "p1"
    assert row.entity_id == wo.id
