"""计量分类 API 集成测试（CRUD + 租户隔离 + 权限 + Meter 关联）。"""

from __future__ import annotations

from sqlalchemy import select

from app.models.company import Company


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _unlock_pro(db):
    """meters 挂 feature gate；把全部公司升 pro 以便创建仪表。"""
    for c in db.execute(select(Company)).scalars().all():
        c.plan = "pro"
        c.subscription_status = "active"
    db.commit()


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post(
        "/api/v1/users",
        headers=_h(admin_token),
        json={"email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "tech@acme.com", "password": "secret123"},
    ).json()["access_token"]


def test_create_and_list_category(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/meter-categories", headers=_h(t), json={"name": "温度", "description": "温度类"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "温度"
    assert r.json()["description"] == "温度类"
    cats = client.get("/api/v1/meter-categories", headers=_h(t)).json()
    assert {c["name"] for c in cats} == {"温度"}


def test_update_and_delete_category(client):
    t = _admin(client)
    cid = client.post(
        "/api/v1/meter-categories", headers=_h(t), json={"name": "温度"}
    ).json()["id"]
    r = client.patch(
        f"/api/v1/meter-categories/{cid}", headers=_h(t), json={"name": "压力"}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "压力"
    assert client.delete(f"/api/v1/meter-categories/{cid}", headers=_h(t)).status_code == 204
    assert client.get("/api/v1/meter-categories", headers=_h(t)).json() == []


def test_requires_auth(client):
    assert client.get("/api/v1/meter-categories").status_code == 401


def test_cross_tenant_category_isolated(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Globex", email="b@globex.com")
    cid = client.post(
        "/api/v1/meter-categories", headers=_h(tb), json={"name": "B类"}
    ).json()["id"]
    assert client.get("/api/v1/meter-categories", headers=_h(ta)).json() == []
    assert (
        client.patch(
            f"/api/v1/meter-categories/{cid}", headers=_h(ta), json={"name": "x"}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/meter-categories/{cid}", headers=_h(ta)).status_code == 404
    )


def test_technician_can_view_but_not_manage(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    # technician 内置角色含 view 不含 manage
    assert client.get("/api/v1/meter-categories", headers=_h(tech)).status_code == 200
    assert (
        client.post(
            "/api/v1/meter-categories", headers=_h(tech), json={"name": "x"}
        ).status_code
        == 403
    )


def test_meter_can_set_and_read_back_category(client, db):
    t = _admin(client)
    _unlock_pro(db)
    cid = client.post(
        "/api/v1/meter-categories", headers=_h(t), json={"name": "温度"}
    ).json()["id"]
    r = client.post(
        "/api/v1/meters",
        headers=_h(t),
        json={"name": "温度表", "unit": "℃", "meter_category_id": cid},
    )
    assert r.status_code == 201, r.text
    assert r.json()["meter_category_id"] == cid
    mid = r.json()["id"]
    # 读回
    assert client.get(f"/api/v1/meters/{mid}", headers=_h(t)).json()["meter_category_id"] == cid
    # 改为空
    upd = client.patch(
        f"/api/v1/meters/{mid}", headers=_h(t), json={"meter_category_id": None}
    )
    assert upd.status_code == 200
    assert upd.json()["meter_category_id"] is None
