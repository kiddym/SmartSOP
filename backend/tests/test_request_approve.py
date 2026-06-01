import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.request_status import RequestStatus
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus
from app.schemas.request import RequestApprove, RequestCreate
from app.services import request_service as svc
from app.services import work_order_service as wos


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def _published_procedure(db, company_id, *, status="PUBLISHED"):
    p = Procedure(
        procedure_group_id="grp-1",
        folder_id="f1",
        code="SOP-A",
        name="SOP-A",
        version=1,
        level_of_use="reference",
        status=status,
        company_id=company_id,
    )
    db.add(p)
    db.flush()
    db.add(
        ProcedureNode(
            procedure_id=p.id,
            sort_order=0,
            heading_level=1,
            kind="node",
            body="章",
            code="C1",
            company_id=company_id,
        )
    )
    db.add(
        ProcedureNode(
            procedure_id=p.id,
            sort_order=1,
            heading_level=None,
            kind="step",
            body="步1",
            code="S1",
            input_schema={},
            company_id=company_id,
        )
    )
    db.commit()
    db.refresh(p)
    return p


def test_approve_copies_fields_and_links(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    r = svc.create_request(
        db,
        RequestCreate(title="漏水", description="厨房", priority=WorkOrderPriority.HIGH),
        c.id,
        actor_user_id=None,
    )
    wo = svc.approve_request(db, r, RequestApprove(note="受理"), c.id, actor_user_id="u9")
    assert r.status == RequestStatus.APPROVED
    assert r.work_order_id == wo.id
    assert wo.request_id == r.id
    assert wo.title == "漏水" and wo.description == "厨房"
    assert wo.priority == WorkOrderPriority.HIGH
    assert wo.status == WorkOrderStatus.OPEN
    assert r.resolved_by_user_id == "u9" and r.resolved_at is not None


def test_approve_with_assignees_and_sop(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    wo = svc.approve_request(
        db,
        r,
        RequestApprove(assignee_ids=["u1", "u2"], procedure_id=p.id),
        c.id,
        actor_user_id="u9",
    )
    assert wo.procedure_id == p.id
    assert set(wos.assignee_ids(db, wo.id)) == {"u1", "u2"}


def test_approve_writes_activities(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    svc.approve_request(db, r, RequestApprove(note="ok"), c.id, actor_user_id="u9")
    acts = svc.list_activities(db, r.id)
    types = {a.activity_type for a in acts}
    assert "STATUS_CHANGE" in types and "WO_GENERATED" in types
    assert any(a.to_status == "APPROVED" for a in acts)


def test_approve_non_pending_rejected(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    svc.cancel_request(db, r, "x", c.id, actor_user_id=None)
    with pytest.raises(HTTPException) as exc:
        svc.approve_request(db, r, RequestApprove(), c.id, actor_user_id=None)
    assert exc.value.status_code == 400


def test_approve_unpublished_sop_rejected(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id, status="DRAFT")
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    with pytest.raises(HTTPException) as exc:
        svc.approve_request(db, r, RequestApprove(procedure_id=p.id), c.id, actor_user_id=None)
    assert exc.value.status_code == 400
