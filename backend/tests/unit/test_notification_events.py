import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder
from app.services import notification_service as svc

CO = "co-1"


def _user(db, uid, role_id=None, status=UserStatus.active):
    db.add(
        User(
            id=uid,
            email=f"{uid}@x.com",
            password_hash="x",
            name=uid,
            status=status,
            role_id=role_id,
            company_id=CO,
        )
    )
    db.commit()


def _wo(db, wid="wo-1", primary=None):
    wo = WorkOrder(id=wid, custom_id="WO1", title="泵维修", primary_user_id=primary, company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_on_wo_assigned_notifies_only_added_active_non_actor(db: Session):
    _user(db, "u1")
    _user(db, "actor")
    wo = _wo(db)
    svc.on_wo_assigned(db, wo, recipient_ids={"u1", "actor"}, actor_user_id="actor")
    db.commit()
    rows = db.execute(select(Notification)).scalars().all()
    assert len(rows) == 1 and rows[0].recipient_user_id == "u1"
    assert rows[0].type == "WO_ASSIGNED"
    assert json.loads(rows[0].params)["custom_id"] == "WO1"


def test_on_wo_status_changed_notifies_recipients(db: Session):
    _user(db, "primary")
    wo = _wo(db, primary="primary")
    svc.on_wo_status_changed(
        db, wo, from_status="OPEN", to_status="IN_PROGRESS", actor_user_id=None
    )
    db.commit()
    row = db.execute(select(Notification)).scalars().one()
    assert row.type == "WO_STATUS_CHANGED"
    p = json.loads(row.params)
    assert p["from_status"] == "OPEN" and p["to_status"] == "IN_PROGRESS"


def test_on_wo_auto_generated_falls_back_to_admins(db: Session):
    db.add(Role(id="r-admin", code="admin", name="A", permissions=[], company_id=CO))
    db.commit()
    _user(db, "boss", role_id="r-admin")
    wo = _wo(db)  # 无指派人
    svc.on_wo_auto_generated(db, wo, actor_user_id=None)
    db.commit()
    rows = db.execute(select(Notification)).scalars().all()
    assert {r.recipient_user_id for r in rows} == {"boss"}
    assert rows[0].type == "WO_AUTO_GENERATED"


def test_on_request_submitted_notifies_approvers(db: Session):
    db.add(
        Role(id="r-appr", code="approver", name="A", permissions=["request.approve"], company_id=CO)
    )
    db.commit()
    _user(db, "appr", role_id="r-appr")

    class _R:  # 轻量替身：on_request_submitted 只读 id/custom_id/title/company_id
        id = "rq-1"
        custom_id = "RQ1"
        title = "申请"
        company_id = CO

    svc.on_request_submitted(db, _R(), actor_user_id=None)
    db.commit()
    row = db.execute(select(Notification)).scalars().one()
    assert row.type == "REQUEST_SUBMITTED" and row.recipient_user_id == "appr"
    assert row.entity_type == "request" and row.entity_id == "rq-1"


def test_on_po_approved_notifies_po_approvers(db: Session):
    db.add(
        Role(id="r-poa", code="po", name="P", permissions=["purchase_order.approve"], company_id=CO)
    )
    db.commit()
    _user(db, "poappr", role_id="r-poa")

    class _PO:
        id = "po-1"
        custom_id = "PO1"
        company_id = CO

    svc.on_po_approved(db, _PO(), actor_user_id=None)
    db.commit()
    row = db.execute(select(Notification)).scalars().one()
    assert row.type == "PO_APPROVED" and row.recipient_user_id == "poappr"
