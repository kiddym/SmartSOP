from app import tenant
from app.models.company import Company
from app.models.node import ProcedureNode
from app.models.procedure import Procedure


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug):
    return db.execute(
        Company.__table__.select().where(Company.slug == slug)
    ).first().id


def _seed_published_procedure(db, company_id):
    """直接经 db 预置 PUBLISHED 程序（client 与 db 共享同一引擎）。"""
    tenant.set_current_company_id(company_id)
    p = Procedure(procedure_group_id="g1", folder_id="f1", code="SOP-1", name="程序",
                  version=1, level_of_use="reference", status="PUBLISHED", company_id=company_id)
    db.add(p)
    db.flush()
    db.add(ProcedureNode(procedure_id=p.id, sort_order=0, heading_level=1, kind="node",
                         body="章", code="C1", company_id=company_id))
    db.add(ProcedureNode(procedure_id=p.id, sort_order=1, heading_level=None, kind="step",
                         body="步1", code="S1", input_schema={}, company_id=company_id))
    db.commit()
    tenant.set_current_company_id(None)
    return p.id


def test_create_list_custom_id(client):
    t = _admin(client)
    a = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "换油"}).json()
    assert a["custom_id"] == "WO000001"
    assert a["status"] == "OPEN"
    titles = {x["title"] for x in client.get("/api/v1/work-orders", headers=_h(t)).json()}
    assert titles == {"换油"}


def test_transition_and_activities(client):
    t = _admin(client)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    r = client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                    json={"to_status": "IN_PROGRESS"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "IN_PROGRESS"
    # 非法转移
    bad = client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                      json={"to_status": "OPEN"})
    assert bad.status_code == 400
    acts = client.get(f"/api/v1/work-orders/{wid}/activities", headers=_h(t)).json()
    assert any(a["activity_type"] == "STATUS_CHANGE" for a in acts)


def test_assignees_and_comment(client):
    t = _admin(client)
    uid = client.post("/api/v1/users", headers=_h(t),
                      json={"email": "w@a.com", "password": "secret123", "name": "W"}).json()["id"]
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    r = client.put(f"/api/v1/work-orders/{wid}/assignees", headers=_h(t), json={"user_ids": [uid]})
    assert set(r.json()["assignee_ids"]) == {uid}
    c = client.post(f"/api/v1/work-orders/{wid}/activities", headers=_h(t),
                    json={"comment": "备件已到"})
    assert c.status_code == 201, c.text


def test_update_and_delete(client):
    t = _admin(client)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    assert client.patch(f"/api/v1/work-orders/{wid}", headers=_h(t),
                        json={"priority": "HIGH"}).json()["priority"] == "HIGH"
    assert client.delete(f"/api/v1/work-orders/{wid}", headers=_h(t)).status_code == 204
    assert client.get("/api/v1/work-orders", headers=_h(t)).json() == []


def test_sop_attach_execute_complete(client, db):
    t = _admin(client)
    cid = _company_id(db, "acme")
    pid = _seed_published_procedure(db, cid)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    # 挂接
    r = client.post(f"/api/v1/work-orders/{wid}/attach-procedure", headers=_h(t),
                    json={"procedure_id": pid})
    assert r.status_code == 200, r.text
    view = client.get(f"/api/v1/work-orders/{wid}/execution", headers=_h(t)).json()
    assert view["procedure"]["code"] == "SOP-1"
    assert len(view["outline"]) == 2 and len(view["steps"]) == 1
    rid = view["steps"][0]["id"]
    # 未到 IN_PROGRESS 不能填
    assert client.patch(f"/api/v1/work-orders/{wid}/steps/{rid}", headers=_h(t),
                        json={"is_done": True}).status_code == 400
    client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                json={"to_status": "IN_PROGRESS"})
    # 有未完成 step 不能 COMPLETE
    assert client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                       json={"to_status": "COMPLETE"}).status_code == 400
    assert client.patch(f"/api/v1/work-orders/{wid}/steps/{rid}", headers=_h(t),
                        json={"is_done": True}).status_code == 200
    assert client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                       json={"to_status": "COMPLETE"}).json()["status"] == "COMPLETE"


def test_attach_twice_conflicts(client, db):
    """spec §4.1/§7：已挂接 SOP 的工单再 attach 返回 409。"""
    t = _admin(client)
    cid = _company_id(db, "acme")
    pid = _seed_published_procedure(db, cid)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    first = client.post(f"/api/v1/work-orders/{wid}/attach-procedure", headers=_h(t),
                        json={"procedure_id": pid})
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/work-orders/{wid}/attach-procedure", headers=_h(t),
                         json={"procedure_id": pid})
    assert second.status_code == 409, second.text


def test_attach_only_published(client, db):
    t = _admin(client)
    cid = _company_id(db, "acme")
    pid = _seed_published_procedure(db, cid)
    # 改为 DRAFT
    tenant.set_current_company_id(cid)
    proc = db.get(Procedure, pid)
    proc.status = "DRAFT"
    db.commit()
    tenant.set_current_company_id(None)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    r = client.post(f"/api/v1/work-orders/{wid}/attach-procedure", headers=_h(t),
                    json={"procedure_id": pid})
    assert r.status_code == 400


def test_requires_auth(client):
    assert client.get("/api/v1/work-orders").status_code == 401


def test_cross_tenant_404(client):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Globex", "b@globex.com")
    bid = client.post("/api/v1/work-orders", headers=_h(tb), json={"title": "B单"}).json()["id"]
    assert client.get(f"/api/v1/work-orders/{bid}", headers=_h(ta)).status_code == 404
    assert client.post(f"/api/v1/work-orders/{bid}/transition", headers=_h(ta),
                       json={"to_status": "IN_PROGRESS"}).status_code == 404


def test_technician_execute_not_delete(client, db):
    admin = _admin(client)
    cid = _company_id(db, "acme")
    pid = _seed_published_procedure(db, cid)
    client.post("/api/v1/users", headers=_h(admin),
                json={"email": "tech@acme.com", "password": "secret123", "name": "T"})
    roles = client.get("/api/v1/roles", headers=_h(admin)).json()
    tech_role = next(r for r in roles if r["code"] == "technician")["id"]
    uid = [u for u in client.get("/api/v1/users", headers=_h(admin)).json()
           if u["email"] == "tech@acme.com"][0]["id"]
    client.patch(f"/api/v1/users/{uid}", headers=_h(admin), json={"role_id": tech_role})
    tech = client.post("/api/v1/auth/login", json={
        "email": "tech@acme.com", "password": "secret123",
        "company_slug": "acme"}).json()["access_token"]
    wid = client.post("/api/v1/work-orders", headers=_h(admin), json={"title": "t"}).json()["id"]
    # technician 不能建单
    assert client.post("/api/v1/work-orders", headers=_h(tech),
                       json={"title": "x"}).status_code == 403
    # 能转状态（edit）
    assert client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(tech),
                       json={"to_status": "IN_PROGRESS"}).status_code == 200
    # 不能删
    assert client.delete(f"/api/v1/work-orders/{wid}", headers=_h(tech)).status_code == 403
