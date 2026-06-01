from app.models.company import Company
from app.models.request import Request
from app.models.request_status import RequestStatus
from app.models.work_order_status import WorkOrderPriority


def test_request_defaults(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    r = Request(custom_id="RQ000001", title="漏水", company_id=c.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    assert r.status == RequestStatus.PENDING
    assert r.priority == WorkOrderPriority.NONE
    assert r.is_active is True
    assert r.work_order_id is None
    assert r.resolution_note == ""
    assert r.id is not None and len(r.id) == 36


def test_request_activity_importable(db):
    from app.models.request_activity import RequestActivity

    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    r = Request(custom_id="RQ000001", title="t", company_id=c.id)
    db.add(r)
    db.commit()
    act = RequestActivity(request_id=r.id, activity_type="COMMENT", comment="hi", company_id=c.id)
    db.add(act)
    db.commit()
    assert act.activity_type == "COMMENT"


def test_work_order_has_request_id(db):
    from app.models.work_order import WorkOrder

    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    wo = WorkOrder(custom_id="WO000001", title="t", company_id=c.id, request_id="req-x")
    db.add(wo)
    db.commit()
    db.refresh(wo)
    assert wo.request_id == "req-x"
