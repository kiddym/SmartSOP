"""/work-orders 扩展：by_asset / by_user / by_category。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.company import Company
from app.models.work_order import WorkOrder


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_distributions(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    db.add(WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co,
                     asset_id="A1", primary_user_id="U1", category_id="C1"))
    db.add(WorkOrder(custom_id="WO2", title="t", created_at=datetime.utcnow(), company_id=co,
                     asset_id="A1", primary_user_id=None, category_id=None))
    db.commit()
    body = client.get("/api/v1/analytics/work-orders", headers=_h(t)).json()
    by_asset = {r["asset_id"]: r["count"] for r in body["by_asset"]}
    assert by_asset["A1"] == 2
    by_user = {r["user_id"]: r["count"] for r in body["by_user"]}
    assert by_user["U1"] == 1 and by_user[None] == 1
    by_cat = {r["category_id"]: r["count"] for r in body["by_category"]}
    assert by_cat["C1"] == 1 and by_cat[None] == 1
