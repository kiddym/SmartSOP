from datetime import date, timedelta

from app import tenant
from app.models.company import Company
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.schemas.work_order import WorkOrderTransition
from app.services import work_order_service as svc


def _wo(db, **kw):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    tenant.set_current_company_id(c.id)
    wo = WorkOrder(custom_id="WO000001", title="t", company_id=c.id, **kw)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return c, wo


def _to(db, wo, status, company_id, actor="u1"):
    return svc.transition(
        db, wo, WorkOrderTransition(to_status=status), company_id, actor_user_id=actor
    )


def test_complete_stamps_completed_by_and_compliant_on_time(db):
    c, wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, due_date=date.today() + timedelta(days=1))
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id, actor="u9")
    assert wo.status == WorkOrderStatus.COMPLETE
    assert wo.completed_by_user_id == "u9"
    assert wo.completed_at is not None
    assert wo.is_compliant is True


def test_complete_overdue_is_not_compliant(db):
    c, wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, due_date=date.today() - timedelta(days=1))
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id)
    assert wo.is_compliant is False


def test_complete_without_due_date_is_compliant(db):
    c, wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, due_date=None)
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id)
    assert wo.is_compliant is True


def test_reopen_clears_completion(db):
    c, wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, due_date=None)
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id, actor="u9")
    _to(db, wo, WorkOrderStatus.IN_PROGRESS, c.id, actor="u3")
    assert wo.completed_at is None
    assert wo.completed_by_user_id is None
    assert wo.is_compliant is None


def test_first_responded_at_set_once_on_leaving_open(db):
    c, wo = _wo(db, status=WorkOrderStatus.OPEN, due_date=None)
    _to(db, wo, WorkOrderStatus.IN_PROGRESS, c.id)
    first = wo.first_responded_at
    assert first is not None
    # 完成再重开，first_responded_at 不被覆盖
    _to(db, wo, WorkOrderStatus.COMPLETE, c.id)
    _to(db, wo, WorkOrderStatus.IN_PROGRESS, c.id)
    assert wo.first_responded_at == first
