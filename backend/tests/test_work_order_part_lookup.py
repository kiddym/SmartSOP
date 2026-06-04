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
    # Acme: WO "A" consumes part p1
    a = client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "A"}).json()["id"]
    tenant.set_current_company_id(cid_a)
    db.add(
        PartConsumption(part_id="p1", work_order_id=a, quantity=1, unit_cost=1, company_id=cid_a)
    )
    db.commit()
    # Beta: WO "B" exists but did NOT consume p1
    client.post("/api/v1/work-orders", headers=_h(tb), json={"title": "B"})
    # Beta querying with Acme's part_id must return nothing (suppress B, don't leak A)
    rows = client.get("/api/v1/work-orders?part_id=p1", headers=_h(tb)).json()
    assert rows == []
    # Sanity: Beta's no-filter list returns its own WO, proving the empty result above is meaningful
    all_rows = client.get("/api/v1/work-orders", headers=_h(tb)).json()
    assert {r["title"] for r in all_rows} == {"B"}


def test_list_part_filter_no_cross_tenant_leak_same_part_id(client, db):
    ta = _admin(client, "Acme", "a@a.com")
    tb = _admin(client, "Beta", "b@b.com")
    cid_a = _company_id(db, "acme")
    cid_b = _company_id(db, "beta")
    # Acme WO "A" consumes literal part_id "p1" under Acme
    a = client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "A"}).json()["id"]
    # Beta WO "B" consumes the SAME literal part_id "p1" but under Beta
    b = client.post("/api/v1/work-orders", headers=_h(tb), json={"title": "B"}).json()["id"]
    tenant.set_current_company_id(cid_a)
    db.add(
        PartConsumption(part_id="p1", work_order_id=a, quantity=1, unit_cost=1, company_id=cid_a)
    )
    db.commit()
    tenant.set_current_company_id(cid_b)
    db.add(
        PartConsumption(part_id="p1", work_order_id=b, quantity=1, unit_cost=1, company_id=cid_b)
    )
    db.commit()
    # Beta querying part_id=p1 sees only its own WO; Acme's A must not leak
    rows = client.get("/api/v1/work-orders?part_id=p1", headers=_h(tb)).json()
    assert {r["title"] for r in rows} == {"B"}
