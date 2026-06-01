from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.schemas.work_order import WorkOrderTransition
from app.services import work_order_service as wos

CO = "co-1"


def _user(db, uid):
    db.add(
        User(
            id=uid,
            email=f"{uid}@x.com",
            password_hash="x",
            name=uid,
            status=UserStatus.active,
            company_id=CO,
        )
    )
    db.commit()


def _wo(db, primary=None, status=WorkOrderStatus.OPEN):
    wo = WorkOrder(
        custom_id="WO1", title="t", status=status, primary_user_id=primary, company_id=CO
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_set_assignees_notifies_newly_added_only(db: Session):
    _user(db, "u1")
    _user(db, "u2")
    wo = _wo(db)
    wos.set_assignees(db, wo, ["u1"], CO, actor_user_id="boss")  # 首次加 u1
    wos.set_assignees(db, wo, ["u1", "u2"], CO, actor_user_id="boss")  # 再加 u2
    rows = (
        db.execute(select(Notification).where(Notification.type == "WO_ASSIGNED")).scalars().all()
    )
    # u1 仅在第一次被通知；第二次仅 u2
    recips = sorted(r.recipient_user_id for r in rows)
    assert recips == ["u1", "u2"]


def test_set_assignees_excludes_actor(db: Session):
    _user(db, "boss")
    wo = _wo(db)
    wos.set_assignees(db, wo, ["boss"], CO, actor_user_id="boss")
    assert db.execute(select(Notification)).scalars().all() == []


def test_transition_notifies_recipients(db: Session):
    _user(db, "primary")
    wo = _wo(db, primary="primary")
    wos.transition(
        db,
        wo,
        WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS, note=""),
        CO,
        actor_user_id=None,
    )
    row = (
        db.execute(select(Notification).where(Notification.type == "WO_STATUS_CHANGED"))
        .scalars()
        .one()
    )
    assert row.recipient_user_id == "primary"
