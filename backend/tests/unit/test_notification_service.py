import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm
from app.models.role import Role
from app.models.team import Team, TeamUser
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.services import notification_service as svc

CO = "co-1"


def _user(db, uid, status=UserStatus.active, role_id=None):
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
    wo = WorkOrder(id=wid, custom_id="WO1", title="t", primary_user_id=primary, company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_notify_one_row_per_recipient(db: Session):
    n = svc.notify(
        db,
        company_id=CO,
        recipient_ids={"u-1", "u-2"},
        type="WO_ASSIGNED",
        entity_type="work_order",
        entity_id="wo-1",
        params={"custom_id": "WO1"},
        actor_user_id=None,
    )
    db.commit()
    assert n == 2
    rows = db.execute(select(Notification)).scalars().all()
    assert {r.recipient_user_id for r in rows} == {"u-1", "u-2"}
    assert json.loads(rows[0].params)["custom_id"] == "WO1"


def test_notify_empty_recipients_noop(db: Session):
    assert (
        svc.notify(
            db,
            company_id=CO,
            recipient_ids=set(),
            type="X",
            entity_type=None,
            entity_id=None,
            params={},
            actor_user_id=None,
        )
        == 0
    )


def test_resolve_wo_recipients_merges_and_filters_active(db: Session):
    _user(db, "primary")
    _user(db, "a1")
    _user(db, "inactive", status=UserStatus.disabled)
    _user(db, "tm1")
    db.add(Team(id="team-1", name="T", company_id=CO))
    db.commit()
    db.add(TeamUser(team_id="team-1", user_id="tm1", company_id=CO))
    wo = _wo(db, primary="primary")
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id="a1", company_id=CO))
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id="inactive", company_id=CO))
    db.add(WorkOrderTeam(work_order_id=wo.id, team_id="team-1", company_id=CO))
    db.commit()
    got = svc.resolve_wo_recipients(db, wo, exclude_actor_id=None)
    assert got == {"primary", "a1", "tm1"}  # inactive 被过滤


def test_resolve_wo_recipients_excludes_actor(db: Session):
    _user(db, "primary")
    _user(db, "a1")
    wo = _wo(db, primary="primary")
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id="a1", company_id=CO))
    db.commit()
    assert svc.resolve_wo_recipients(db, wo, exclude_actor_id="a1") == {"primary"}


def test_resolve_permission_holders_by_code(db: Session):
    db.add(
        Role(id="r-appr", code="approver", name="A", permissions=["request.approve"], company_id=CO)
    )
    db.add(
        Role(
            id="r-tech", code="technician", name="T", permissions=["work_order.view"], company_id=CO
        )
    )
    db.commit()
    _user(db, "appr", role_id="r-appr")
    _user(db, "tech", role_id="r-tech")
    _user(db, "appr_off", status=UserStatus.disabled, role_id="r-appr")
    got = svc.resolve_permission_holders(db, CO, "request.approve", exclude_actor_id=None)
    assert got == {"appr"}  # 仅活跃且有该权限


def test_resolve_permission_holders_super_admin_wildcard(db: Session):
    db.add(Role(id="r-sa", code="super_admin", name="SA", permissions=[], company_id=CO))
    db.commit()
    _user(db, "sa", role_id="r-sa")
    # super_admin 通配 ALL_PERMISSIONS（含 part.edit）
    assert "sa" in svc.resolve_permission_holders(db, CO, "part.edit", exclude_actor_id=None)


def test_arm_disarm_cycle(db: Session):
    assert svc.is_armed(db, CO, "K1") is False
    svc.arm(db, CO, "K1")
    db.commit()
    assert svc.is_armed(db, CO, "K1") is True
    svc.disarm(db, CO, "K1")
    db.commit()
    assert svc.is_armed(db, CO, "K1") is False
    assert db.execute(select(NotificationArm)).scalars().all() == []
