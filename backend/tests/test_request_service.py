import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.models.request_status import RequestStatus
from app.schemas.request import RequestCreate, RequestUpdate
from app.services import request_service as svc


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def _ctx(company_id):
    tenant.set_current_company_id(company_id)


def test_create_assigns_custom_id(db):
    c = _company(db, "acme")
    _ctx(c.id)
    a = svc.create_request(db, RequestCreate(title="漏水1"), c.id, actor_user_id=None)
    b = svc.create_request(db, RequestCreate(title="漏水2"), c.id, actor_user_id=None)
    assert a.custom_id == "RQ000001"
    assert b.custom_id == "RQ000002"
    assert a.status == RequestStatus.PENDING


def test_tenants_independent_custom_id(db):
    c1 = _company(db, "acme")
    c2 = _company(db, "globex")
    _ctx(c1.id)
    a = svc.create_request(db, RequestCreate(title="x"), c1.id, actor_user_id=None)
    _ctx(c2.id)
    b = svc.create_request(db, RequestCreate(title="y"), c2.id, actor_user_id=None)
    assert a.custom_id == "RQ000001" and b.custom_id == "RQ000001"


def test_update_only_when_pending(db):
    c = _company(db, "acme")
    _ctx(c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    svc.update_request(db, r, RequestUpdate(title="t2"))
    assert r.title == "t2"
    svc.reject_request(db, r, "重复", c.id, actor_user_id="u1")
    with pytest.raises(HTTPException) as exc:
        svc.update_request(db, r, RequestUpdate(title="t3"))
    assert exc.value.status_code == 400


def test_reject_sets_fields_and_activity(db):
    c = _company(db, "acme")
    _ctx(c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    svc.reject_request(db, r, "不在保修范围", c.id, actor_user_id="u9")
    assert r.status == RequestStatus.REJECTED
    assert r.resolution_note == "不在保修范围"
    assert r.resolved_by_user_id == "u9" and r.resolved_at is not None
    acts = svc.list_activities(db, r.id)
    assert any(a.activity_type == "STATUS_CHANGE" and a.to_status == "REJECTED" for a in acts)


def test_cancel_sets_fields_and_activity(db):
    c = _company(db, "acme")
    _ctx(c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    svc.cancel_request(db, r, "误报", c.id, actor_user_id="u3")
    assert r.status == RequestStatus.CANCELED
    assert r.resolution_note == "误报"
    acts = svc.list_activities(db, r.id)
    assert any(a.activity_type == "STATUS_CHANGE" and a.to_status == "CANCELED" for a in acts)


def test_reject_non_pending_rejected(db):
    c = _company(db, "acme")
    _ctx(c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    svc.cancel_request(db, r, "x", c.id, actor_user_id=None)
    with pytest.raises(HTTPException) as exc:
        svc.reject_request(db, r, "y", c.id, actor_user_id=None)
    assert exc.value.status_code == 400


def test_soft_delete(db):
    c = _company(db, "acme")
    _ctx(c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    svc.delete_request(db, r)
    assert r.is_active is False
    assert svc.get_request(db, r.id) is None


def test_list_pending_only(db):
    c = _company(db, "acme")
    _ctx(c.id)
    a = svc.create_request(db, RequestCreate(title="a"), c.id, actor_user_id=None)
    b = svc.create_request(db, RequestCreate(title="b"), c.id, actor_user_id=None)
    svc.cancel_request(db, b, "x", c.id, actor_user_id=None)
    pending = svc.list_requests(db, status=RequestStatus.PENDING.value)
    assert {r.id for r in pending} == {a.id}


def test_comment_activity(db):
    c = _company(db, "acme")
    _ctx(c.id)
    r = svc.create_request(db, RequestCreate(title="t"), c.id, actor_user_id=None)
    svc.add_comment(db, r, "请尽快", c.id, actor_user_id="u3")
    acts = svc.list_activities(db, r.id)
    assert any(a.activity_type == "COMMENT" and a.comment == "请尽快" for a in acts)
