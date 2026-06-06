"""反查端点：工单列表按 asset_id/location_id 过滤；/parts/{id}/work-orders 经消耗去重。"""

from app import tenant
from app.models.part_consumption import PartConsumption


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


def test_list_filter_by_asset(client):
    t = _admin(client)
    h = _h(t)
    a = client.post("/api/v1/assets", headers=h, json={"name": "泵"}).json()["id"]
    client.post("/api/v1/work-orders", headers=h, json={"title": "OnAsset", "asset_id": a})
    client.post("/api/v1/work-orders", headers=h, json={"title": "NoAsset"})
    rows = client.get(f"/api/v1/work-orders?asset_id={a}", headers=h).json()
    assert {r["title"] for r in rows} == {"OnAsset"}


def test_list_filter_by_location(client):
    t = _admin(client)
    h = _h(t)
    loc = client.post("/api/v1/locations", headers=h, json={"name": "车间"}).json()["id"]
    client.post("/api/v1/work-orders", headers=h, json={"title": "OnLoc", "location_id": loc})
    client.post("/api/v1/work-orders", headers=h, json={"title": "NoLoc"})
    rows = client.get(f"/api/v1/work-orders?location_id={loc}", headers=h).json()
    assert {r["title"] for r in rows} == {"OnLoc"}


def test_part_work_orders_endpoint_dedup(client, db):
    t = _admin(client)
    h = _h(t)
    cid = _company_id(db, "acme")
    part = client.post(
        "/api/v1/parts", headers=h, json={"name": "轴承", "quantity": 10, "min_quantity": 1}
    ).json()["id"]
    a = client.post("/api/v1/work-orders", headers=h, json={"title": "Consumer"}).json()["id"]
    client.post("/api/v1/work-orders", headers=h, json={"title": "NonConsumer"})
    tenant.set_current_company_id(cid)
    # two consumptions of the same part on the same WO -> WO appears once
    db.add(
        PartConsumption(part_id=part, work_order_id=a, quantity=1, unit_cost=1, company_id=cid)
    )
    db.add(
        PartConsumption(part_id=part, work_order_id=a, quantity=2, unit_cost=1, company_id=cid)
    )
    db.commit()
    rows = client.get(f"/api/v1/parts/{part}/work-orders", headers=h).json()
    assert [r["title"] for r in rows] == ["Consumer"]


def test_part_work_orders_cross_tenant_404(client):
    t1 = _admin(client, "Acme", "a@acme.com")
    part = client.post(
        "/api/v1/parts",
        headers=_h(t1),
        json={"name": "轴承", "quantity": 1, "min_quantity": 1},
    ).json()["id"]
    t2 = _admin(client, "Beta", "b@beta.com")
    r = client.get(f"/api/v1/parts/{part}/work-orders", headers=_h(t2))
    assert r.status_code == 404, r.text
