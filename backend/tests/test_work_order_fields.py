from datetime import date

from app import tenant
from app.models.company import Company
from app.models.work_order import WorkOrder
from app.services import work_order_service as svc


def _company(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    return c


def test_new_fields_default(db):
    c = _company(db)
    tenant.set_current_company_id(c.id)
    wo = WorkOrder(custom_id="WO000001", title="t", company_id=c.id)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    assert wo.completed_by_user_id is None
    assert wo.feedback is None
    assert wo.urgent is False
    assert wo.estimated_duration is None
    assert wo.estimated_start_date is None
    assert wo.first_responded_at is None
    assert wo.archived is False
    assert wo.is_compliant is None


def test_to_read_includes_new_fields(db):
    c = _company(db)
    tenant.set_current_company_id(c.id)
    wo = WorkOrder(
        custom_id="WO000001",
        title="t",
        company_id=c.id,
        urgent=True,
        feedback="ok",
        estimated_duration=90,
        estimated_start_date=date(2026, 6, 10),
        archived=True,
    )
    db.add(wo)
    db.commit()
    data = svc.to_read(db, wo)
    assert data["urgent"] is True
    assert data["feedback"] == "ok"
    assert data["estimated_duration"] == 90
    assert data["estimated_start_date"] == date(2026, 6, 10)
    assert data["archived"] is True
    assert data["completed_by_user_id"] is None
    assert data["first_responded_at"] is None
    assert data["is_compliant"] is None
