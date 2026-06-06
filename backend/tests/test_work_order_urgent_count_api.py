"""工单 urgent 计数端点：仅计 urgent 且未完成/未取消，租户隔离。

注：urgent 字段非 WorkOrderUpdate 可写字段（2B 仅暴露于读模型），故测试经 ORM 直设。
"""

from app import tenant
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug):
    from app.models.company import Company

    return db.execute(Company.__table__.select().where(Company.slug == slug)).first().id


def _mk(client, h, title):
    return client.post("/api/v1/work-orders", headers=h, json={"title": title}).json()["id"]


def _set_urgent(db, cid, wid, value=True):
    tenant.set_current_company_id(cid)
    db.get(WorkOrder, wid).urgent = value
    db.commit()


def _transition(client, h, wid, to_status):
    return client.post(
        f"/api/v1/work-orders/{wid}/transition", headers=h, json={"to_status": to_status}
    )


def test_urgent_count_counts_only_open_urgent(client, db):
    t = _admin(client)
    h = _h(t)
    cid = _company_id(db, "acme")
    u1 = _mk(client, h, "U1")
    u2 = _mk(client, h, "U2")
    _mk(client, h, "Plain")  # non-urgent
    _set_urgent(db, cid, u1)
    _set_urgent(db, cid, u2)
    r = client.get("/api/v1/work-orders/urgent-count", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"count": 2}


def test_urgent_count_excludes_complete_and_canceled(client, db):
    t = _admin(client)
    h = _h(t)
    cid = _company_id(db, "acme")
    keep = _mk(client, h, "Keep")
    done = _mk(client, h, "Done")
    gone = _mk(client, h, "Gone")
    for wid in (keep, done, gone):
        _set_urgent(db, cid, wid)
    # Done -> IN_PROGRESS -> COMPLETE
    _transition(client, h, done, WorkOrderStatus.IN_PROGRESS.value)
    _transition(client, h, done, WorkOrderStatus.COMPLETE.value)
    # Gone -> CANCELED
    _transition(client, h, gone, WorkOrderStatus.CANCELED.value)
    r = client.get("/api/v1/work-orders/urgent-count", headers=h)
    assert r.json() == {"count": 1}
    assert keep  # keep referenced


def test_urgent_count_tenant_isolated(client, db):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Beta", "b@beta.com")
    cid_a = _company_id(db, "acme")
    cid_b = _company_id(db, "beta")
    _set_urgent(db, cid_a, _mk(client, _h(ta), "AcmeUrgent"))
    _set_urgent(db, cid_a, _mk(client, _h(ta), "AcmeUrgent2"))
    _set_urgent(db, cid_b, _mk(client, _h(tb), "BetaUrgent"))
    assert client.get("/api/v1/work-orders/urgent-count", headers=_h(ta)).json() == {"count": 2}
    assert client.get("/api/v1/work-orders/urgent-count", headers=_h(tb)).json() == {"count": 1}
