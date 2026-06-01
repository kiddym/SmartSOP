from app import tenant
from app.models.company import Company
from app.models.node import ProcedureNode
from app.models.procedure import Procedure


def _register(client, company, email):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug):
    return db.execute(Company.__table__.select().where(Company.slug == slug)).first().id


def test_work_orders_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "A单"})
    bid = client.post("/api/v1/work-orders", headers=_h(tb), json={"title": "B单"}).json()["id"]
    a_titles = {x["title"] for x in client.get("/api/v1/work-orders", headers=_h(ta)).json()}
    assert a_titles == {"A单"}
    assert client.get(f"/api/v1/work-orders/{bid}", headers=_h(ta)).status_code == 404
    assert (
        client.patch(
            f"/api/v1/work-orders/{bid}", headers=_h(ta), json={"title": "hack"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/work-orders/{bid}", headers=_h(ta)).status_code == 404
    assert (
        client.post(
            f"/api/v1/work-orders/{bid}/transition",
            headers=_h(ta),
            json={"to_status": "IN_PROGRESS"},
        ).status_code
        == 404
    )


def test_custom_id_per_tenant_independent(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    a1 = client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "x"}).json()["custom_id"]
    b1 = client.post("/api/v1/work-orders", headers=_h(tb), json={"title": "y"}).json()["custom_id"]
    assert a1 == "WO000001" and b1 == "WO000001"


def test_cross_tenant_cannot_attach_others_procedure(client, db):
    ta = _register(client, "Acme", "a@acme.com")
    _register(client, "Globex", "b@globex.com")
    # B 租户的程序
    bcid = _company_id(db, "globex")
    tenant.set_current_company_id(bcid)
    p = Procedure(
        procedure_group_id="g1",
        folder_id="f1",
        code="SOP-B",
        name="B程序",
        version=1,
        level_of_use="reference",
        status="PUBLISHED",
        company_id=bcid,
    )
    db.add(p)
    db.flush()
    db.add(
        ProcedureNode(
            procedure_id=p.id,
            sort_order=0,
            heading_level=None,
            kind="step",
            body="s",
            code="S1",
            input_schema={},
            company_id=bcid,
        )
    )
    db.commit()
    tenant.set_current_company_id(None)
    # A 租户建单并尝试挂 B 的程序 -> 404（跨租户读不可见）
    wid = client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "t"}).json()["id"]
    r = client.post(
        f"/api/v1/work-orders/{wid}/attach-procedure", headers=_h(ta), json={"procedure_id": p.id}
    )
    assert r.status_code == 404
