from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.pm_frequency import PMFrequencyUnit
from app.models.work_order import WorkOrder
from app.schemas.pm import PMCreate
from app.services import pm_service as svc
from app.tasks import pm_generate


def _mk(db, company, **kw):
    base = dict(title="月检", start_date=date(2026, 1, 1),
                frequency_unit=PMFrequencyUnit.DAY, frequency_value=7)
    base.update(kw)
    return svc.create_pm(db, PMCreate(**base), company, actor_user_id=None)


def test_run_generates_for_due_and_advances(db: Session):
    pm = _mk(db, "co-1")
    summary = pm_generate.run(db, now=datetime(2026, 6, 1, 2, 0))
    assert summary["scanned"] == 1 and summary["generated"] == 1 and summary["errors"] == 0
    db.refresh(pm)
    assert pm.next_due_date > date(2026, 6, 1)
    assert db.query(WorkOrder).count() == 1


def test_run_skips_future_and_disabled(db: Session):
    _mk(db, "co-1", start_date=date(2026, 12, 1))           # 未来
    disabled = _mk(db, "co-1", start_date=date(2026, 1, 1))
    svc.disable_pm(db, disabled, "co-1", actor_user_id=None)
    summary = pm_generate.run(db, now=datetime(2026, 6, 1, 2, 0))
    assert summary["scanned"] == 0 and summary["generated"] == 0


def test_run_is_cross_tenant(db: Session):
    _mk(db, "co-1")
    _mk(db, "co-2")
    summary = pm_generate.run(db, now=datetime(2026, 6, 1, 2, 0))
    assert summary["generated"] == 2
    # 各自盖对租户章
    cos = {wo.company_id for wo in db.query(WorkOrder).all()}
    assert cos == {"co-1", "co-2"}


def test_run_cli_once(db: Session):
    assert pm_generate.main(["--once"]) == 0
