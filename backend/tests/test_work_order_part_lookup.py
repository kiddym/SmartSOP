from app import tenant
from app.models.part_consumption import PartConsumption


def _admin(client, company="Acme", email="a@a.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug):
    from app.models.company import Company

    return db.execute(Company.__table__.select().where(Company.slug == slug)).first().id


def test_list_filtered_by_part(client, db):
    t = _admin(client)
    h = _h(t)
    cid = _company_id(db, "acme")
    a = client.post("/api/v1/work-orders", headers=h, json={"title": "A"}).json()["id"]
    client.post("/api/v1/work-orders", headers=h, json={"title": "B"})
    tenant.set_current_company_id(cid)
    db.add(PartConsumption(part_id="p1", work_order_id=a, quantity=1, unit_cost=1, company_id=cid))
    db.commit()
    rows = client.get("/api/v1/work-orders?part_id=p1", headers=h).json()
    assert {r["title"] for r in rows} == {"A"}


def test_list_part_filter_tenant_isolated(client, db):
    ta = _admin(client, "Acme", "a@a.com")
    tb = _admin(client, "Beta", "b@b.com")
    cid_a = _company_id(db, "acme")
    a = client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "A"}).json()["id"]
    tenant.set_current_company_id(cid_a)
    db.add(
        PartConsumption(part_id="p1", work_order_id=a, quantity=1, unit_cost=1, company_id=cid_a)
    )
    db.commit()
    rows = client.get("/api/v1/work-orders?part_id=p1", headers=_h(tb)).json()
    assert rows == []
