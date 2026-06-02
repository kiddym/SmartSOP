"""/analytics/personnel：created/completed/assigned/labor_hours/labor_cost。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.company import Company
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderAssignee
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_labor import WorkOrderLabor
from app.models.work_order_status import WorkOrderStatus


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def _user_id(db, email):
    return db.execute(select(User).where(User.email == email)).scalar_one().id


def test_personnel_metrics(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    uid = _user_id(db, "a@acme.com")
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co,
                   created_by_user_id=uid)
    db.add(wo)
    db.flush()
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=uid, company_id=co))
    db.add(WorkOrderActivity(work_order_id=wo.id, activity_type="STATUS_CHANGE",
                             to_status=WorkOrderStatus.COMPLETE.value, actor_user_id=uid,
                             company_id=co))
    db.add(WorkOrderLabor(work_order_id=wo.id, duration_seconds=3600, hourly_rate=Decimal("60"),
                          user_id=uid, company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/personnel", headers=_h(t)).json()
    row = next(r for r in body["users"] if r["user_id"] == uid)
    assert row["name"] == "Admin"
    assert row["created_count"] == 1
    assert row["completed_count"] == 1
    assert row["assigned_count"] == 1
    assert row["labor_hours"] == 1.0
    assert row["labor_cost"] == "60.00"


def test_personnel_tenant_isolation(client, db):
    """B 公司的人员/工单不应出现在 A 公司的统计里。"""
    ta = _admin(client)
    co_a = _company_id(db, "acme")
    uid_a = _user_id(db, "a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    co_b = _company_id(db, "beta")
    uid_b = _user_id(db, "b@beta.com")
    db.add(WorkOrder(custom_id="WOA", title="a", created_at=datetime.utcnow(), company_id=co_a,
                     created_by_user_id=uid_a))
    db.add(WorkOrder(custom_id="WOB", title="b", created_at=datetime.utcnow(), company_id=co_b,
                     created_by_user_id=uid_b))
    db.commit()
    body_a = client.get("/api/v1/analytics/personnel", headers=_h(ta)).json()
    assert {r["user_id"] for r in body_a["users"]} == {uid_a}
    body_b = client.get("/api/v1/analytics/personnel", headers=_h(tb)).json()
    assert {r["user_id"] for r in body_b["users"]} == {uid_b}


def test_requires_auth(client):
    assert client.get("/api/v1/analytics/personnel").status_code == 401
