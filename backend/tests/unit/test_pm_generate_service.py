from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.pm_frequency import PMFrequencyUnit
from app.models.work_order import WorkOrder
from app.schemas.pm import PMCreate
from app.services import pm_service as svc

CO = "co-1"


def _mk(db, **kw):
    base = dict(
        title="月检",
        start_date=date(2026, 6, 1),
        frequency_unit=PMFrequencyUnit.MONTH,
        frequency_value=1,
    )
    base.update(kw)
    return svc.create_pm(db, PMCreate(**base), CO, actor_user_id="a")


def test_generate_once_creates_wo_and_advances(db: Session):
    pm = _mk(db, frequency_unit=PMFrequencyUnit.DAY, frequency_value=7)
    now = datetime(2026, 6, 1, 9, 0, 0)
    wo = svc.generate_once(db, pm, actor_user_id=None, now=now, enforce_due=True)
    assert isinstance(wo, WorkOrder)
    assert wo.due_date == date(2026, 6, 1)  # WO due = 本期计划日
    assert pm.next_due_date == date(2026, 6, 8)  # 锥摆推进一期
    assert pm.last_work_order_id == wo.id
    assert pm.last_generated_at == now
    types = [a.activity_type for a in svc.list_activities(db, pm.id)]
    assert "WO_GENERATED" in types


def test_generate_once_copies_presets(db: Session):
    from app.models.work_order import WorkOrderAssignee, WorkOrderTeam

    pm = _mk(db, assignee_ids=["u-1"], team_ids=["t-1"], primary_user_id="pu")
    wo = svc.generate_once(
        db, pm, actor_user_id=None, now=datetime(2026, 6, 1, 9, 0), enforce_due=True
    )
    a = db.query(WorkOrderAssignee).filter_by(work_order_id=wo.id).all()
    t = db.query(WorkOrderTeam).filter_by(work_order_id=wo.id).all()
    assert {x.user_id for x in a} == {"u-1"}
    assert {x.team_id for x in t} == {"t-1"}
    assert wo.primary_user_id == "pu"


def test_generate_once_enforce_due_rejects_future(db: Session):
    pm = _mk(db, start_date=date(2026, 12, 1))  # next_due 在未来
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        svc.generate_once(
            db, pm, actor_user_id=None, now=datetime(2026, 6, 1, 9, 0), enforce_due=True
        )


def test_generate_once_manual_allows_future_no_advance(db: Session):
    pm = _mk(db, start_date=date(2026, 12, 1))
    before = pm.next_due_date
    wo = svc.generate_once(
        db, pm, actor_user_id="a", now=datetime(2026, 6, 1, 9, 0), enforce_due=False
    )
    # E6：工单 due_date 锚定生成日(+due_date_delay)，非 next_due_date。
    assert wo is not None
    assert wo.due_date == date(2026, 6, 1)
    assert pm.next_due_date == before  # 未到期手动生成不推进（§3.3 no-op）


def test_due_candidates_filters(db: Session):
    due = _mk(db, start_date=date(2026, 1, 1))  # 过去 -> 到期
    future = _mk(db, start_date=date(2026, 12, 1))  # 未来
    disabled = _mk(db, start_date=date(2026, 1, 1))
    svc.disable_pm(db, disabled, CO, actor_user_id="a")
    ids = set(svc.due_candidates(db, today=date(2026, 6, 1)))
    assert due.id in ids
    assert future.id not in ids and disabled.id not in ids
