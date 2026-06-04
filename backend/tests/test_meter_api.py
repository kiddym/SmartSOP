"""Meter API 集成测试（Phase 2C）。经 auth API 建主体，不手工 db.add(User)。"""

from __future__ import annotations

from sqlalchemy import select

from app.models.company import Company


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _unlock_pro(db):
    """meters 已挂 feature gate；把全部公司升 pro 让既有用例可访问。"""
    for c in db.execute(select(Company)).scalars().all():
        c.plan = "pro"
        c.subscription_status = "active"
    db.commit()


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


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


def _meter(client, token, **kw):
    body = {"name": "温度表", "unit": "℃"}
    body.update(kw)
    return client.post("/api/v1/meters", json=body, headers=_h(token))


def _trigger_body(**kw):
    body = {"name": "高温", "comparator": "MORE_THAN", "threshold": "100", "title": "处理高温"}
    body.update(kw)
    return body


def test_meter_crud(client, db):
    t = _admin(client)
    _unlock_pro(db)
    r = _meter(client, t)
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert r.json()["custom_id"] == "MTR000001"
    got = client.get(f"/api/v1/meters/{mid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["unit"] == "℃"
    upd = client.patch(f"/api/v1/meters/{mid}", json={"name": "改名"}, headers=_h(t))
    assert upd.json()["name"] == "改名"
    assert client.delete(f"/api/v1/meters/{mid}", headers=_h(t)).status_code == 204


def test_trigger_crud_and_enable_disable(client, db):
    t = _admin(client)
    _unlock_pro(db)
    mid = _meter(client, t).json()["id"]
    r = client.post(f"/api/v1/meters/{mid}/triggers", json=_trigger_body(), headers=_h(t))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert r.json()["is_armed"] is True
    assert (
        client.post(f"/api/v1/meters/{mid}/triggers/{tid}/disable", headers=_h(t)).json()[
            "is_enabled"
        ]
        is False
    )
    assert (
        client.post(f"/api/v1/meters/{mid}/triggers/{tid}/enable", headers=_h(t)).json()[
            "is_enabled"
        ]
        is True
    )
    lst = client.get(f"/api/v1/meters/{mid}/triggers", headers=_h(t))
    assert len(lst.json()) == 1


def test_submit_reading_fires_and_returns_wo_ids(client, db):
    t = _admin(client)
    _unlock_pro(db)
    mid = _meter(client, t).json()["id"]
    client.post(
        f"/api/v1/meters/{mid}/triggers", json=_trigger_body(assignee_ids=["x"]), headers=_h(t)
    )
    r = client.post(f"/api/v1/meters/{mid}/readings", json={"value": "150"}, headers=_h(t))
    assert r.status_code == 201, r.text
    assert len(r.json()["generated_work_order_ids"]) == 1
    # 读数列表可见
    readings = client.get(f"/api/v1/meters/{mid}/readings", headers=_h(t))
    assert len(readings.json()) == 1


def test_technician_can_read_but_not_configure(client, db):
    admin = _admin(client)
    _unlock_pro(db)
    tech = _technician_token(client, admin)
    mid = _meter(client, admin).json()["id"]
    # 不能建仪表
    assert _meter(client, tech, name="x").status_code == 403
    # 不能建触发器
    assert (
        client.post(
            f"/api/v1/meters/{mid}/triggers", json=_trigger_body(), headers=_h(tech)
        ).status_code
        == 403
    )
    # 能提交读数
    assert (
        client.post(
            f"/api/v1/meters/{mid}/readings", json={"value": "1"}, headers=_h(tech)
        ).status_code
        == 201
    )


def test_tenant_isolation(client, db):
    a = _admin(client)
    _unlock_pro(db)
    mid = _meter(client, a).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    _unlock_pro(db)
    assert client.get(f"/api/v1/meters/{mid}", headers=_h(b)).status_code == 404
