from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm
from app.models.part import Part
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.tasks import due_reminder

CO = "co-1"
NOW = datetime(2026, 1, 15, 8, 0, 0)
TODAY = NOW.date()


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


def _wo(db, *, wid, due, status=WorkOrderStatus.OPEN, primary="p1"):
    wo = WorkOrder(
        id=wid,
        custom_id=wid,
        title="t",
        status=status,
        due_date=due,
        primary_user_id=primary,
        company_id=CO,
    )
    db.add(wo)
    db.commit()
    return wo


def test_due_soon_fires_once_and_arms(db: Session):
    _user(db, "p1")
    _wo(db, wid="wo-soon", due=TODAY + timedelta(days=2))  # 在 [today, today+3)
    due_reminder.run(db, now=NOW)
    rows = (
        db.execute(select(Notification).where(Notification.type == "WO_DUE_SOON")).scalars().all()
    )
    assert len(rows) == 1 and rows[0].recipient_user_id == "p1"
    assert rows[0].dedup_key == f"WO_DUE_SOON:wo-soon:{(TODAY + timedelta(days=2)).isoformat()}"
    # 第二次 tick 不重复（已 armed）
    due_reminder.run(db, now=NOW)
    assert (
        len(
            db.execute(select(Notification).where(Notification.type == "WO_DUE_SOON"))
            .scalars()
            .all()
        )
        == 1
    )


def test_overdue_fires(db: Session):
    _user(db, "p1")
    _wo(db, wid="wo-late", due=TODAY - timedelta(days=1))
    due_reminder.run(db, now=NOW)
    rows = db.execute(select(Notification).where(Notification.type == "WO_OVERDUE")).scalars().all()
    assert len(rows) == 1


def test_terminal_status_excluded(db: Session):
    _user(db, "p1")
    _wo(db, wid="wo-done", due=TODAY - timedelta(days=1), status=WorkOrderStatus.COMPLETE)
    due_reminder.run(db, now=NOW)
    assert db.execute(select(Notification)).scalars().all() == []


def test_due_date_change_rearms(db: Session):
    _user(db, "p1")
    wo = _wo(db, wid="wo-x", due=TODAY + timedelta(days=2))
    due_reminder.run(db, now=NOW)
    # 改期到另一天 -> 旧 arm 失配应被 disarm，新条件再 fire
    wo.due_date = TODAY + timedelta(days=1)
    db.commit()
    due_reminder.run(db, now=NOW)
    keys = {a.key for a in db.execute(select(NotificationArm)).scalars().all()}
    assert keys == {f"WO_DUE_SOON:wo-x:{(TODAY + timedelta(days=1)).isoformat()}"}
    assert (
        len(
            db.execute(select(Notification).where(Notification.type == "WO_DUE_SOON"))
            .scalars()
            .all()
        )
        == 2
    )


def test_low_stock_edge(db: Session):
    db.add(
        Part(
            id="pt-1",
            custom_id="PRT1",
            name="轴承",
            cost=Decimal("0"),
            quantity=Decimal("1"),
            min_quantity=Decimal("5"),
            company_id=CO,
        )
    )
    db.commit()
    due_reminder.run(db, now=NOW)  # 无接收人也 arm（无 part.edit 用户）
    assert {a.key for a in db.execute(select(NotificationArm)).scalars().all()} == {
        "PART_LOW_STOCK:pt-1"
    }
    # 回升 -> disarm
    p = db.get(Part, "pt-1")
    p.quantity = Decimal("9")
    db.commit()
    due_reminder.run(db, now=NOW)
    assert (
        db.execute(select(NotificationArm).where(NotificationArm.key == "PART_LOW_STOCK:pt-1"))
        .scalars()
        .all()
        == []
    )
