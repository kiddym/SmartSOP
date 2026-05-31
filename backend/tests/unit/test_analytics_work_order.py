from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus
from app.services.analytics import work_order_analytics as svc

CO = "co-1"


def _wo(db, *, status=WorkOrderStatus.OPEN, priority=WorkOrderPriority.NONE,
        created, completed_at=None, due_date=None, asset_id=None, location_id=None,
        custom_id="WO000001"):
    wo = WorkOrder(custom_id=custom_id, title="t", status=status, priority=priority,
                   created_at=created, completed_at=completed_at, due_date=due_date,
                   asset_id=asset_id, location_id=location_id, company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_empty_window_zeroes(db: Session):
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["total"] == 0 and r["completion_rate"] == 0.0
    assert r["avg_cycle_time_hours"] is None and r["avg_response_time_hours"] is None
    assert set(r["by_status"]) == {s.value for s in WorkOrderStatus}


def test_counts_and_completion_rate(db: Session):
    base = datetime(2026, 1, 10, 8)
    _wo(db, status=WorkOrderStatus.COMPLETE, priority=WorkOrderPriority.HIGH,
        created=base, completed_at=base + timedelta(hours=10), custom_id="WO1")
    _wo(db, status=WorkOrderStatus.OPEN, created=base, custom_id="WO2")
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["total"] == 2 and r["completed"] == 1 and r["completion_rate"] == 0.5
    assert r["by_status"]["COMPLETE"] == 1 and r["by_status"]["OPEN"] == 1
    assert r["by_priority"]["HIGH"] == 1
    assert r["avg_cycle_time_hours"] == 10.0


def test_window_excludes_outside(db: Session):
    _wo(db, created=datetime(2025, 12, 1), custom_id="OLD")
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["total"] == 0


def test_overdue_as_of_date_to(db: Session):
    base = datetime(2026, 1, 5)
    _wo(db, status=WorkOrderStatus.OPEN, created=base, due_date=date(2026, 1, 10), custom_id="A")
    _wo(db, status=WorkOrderStatus.COMPLETE, created=base, due_date=date(2026, 1, 10),
        completed_at=base, custom_id="B")  # 终态不算逾期
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["overdue"] == 1


def test_response_time_from_first_in_progress(db: Session):
    base = datetime(2026, 1, 10, 8)
    wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, created=base, custom_id="R")
    db.add(WorkOrderActivity(work_order_id=wo.id, activity_type="STATUS_CHANGE",
                             to_status="IN_PROGRESS", created_at=base + timedelta(hours=2),
                             company_id=CO))
    db.add(WorkOrderActivity(work_order_id=wo.id, activity_type="STATUS_CHANGE",
                             to_status="IN_PROGRESS", created_at=base + timedelta(hours=5),
                             company_id=CO))  # 取最早一条
    db.commit()
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["avg_response_time_hours"] == 2.0


def test_filter_by_asset(db: Session):
    base = datetime(2026, 1, 10)
    _wo(db, created=base, asset_id="a-1", custom_id="X")
    _wo(db, created=base, asset_id="a-2", custom_id="Y")
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31),
                                 asset_id="a-1")
    assert r["total"] == 1
