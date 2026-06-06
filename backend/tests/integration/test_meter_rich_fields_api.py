"""计量富字段集成测试：image_url 标量 + 关注人 user_ids（M:N）。

meters 挂 pro feature gate，需先升 pro。user_ids 全量替换：None=不改 / []=清空；
跨租户 user 被拒（404）。
"""

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
    for c in db.execute(select(Company)).scalars().all():
        c.plan = "pro"
        c.subscription_status = "active"
    db.commit()


def _make_user(client, admin_token, *, email):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    return client.post(
        "/api/v1/users",
        headers=_h(admin_token),
        json={"email": email, "password": "secret123", "name": email, "role_id": rid},
    ).json()["id"]


def test_create_meter_with_image_url(client, db):
    t = _admin(client)
    _unlock_pro(db)
    r = client.post(
        "/api/v1/meters",
        headers=_h(t),
        json={"name": "温度表", "unit": "℃", "image_url": "https://img/x.png"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["image_url"] == "https://img/x.png"
    assert r.json()["user_ids"] == []
    mid = r.json()["id"]
    assert client.get(f"/api/v1/meters/{mid}", headers=_h(t)).json()["image_url"] == (
        "https://img/x.png"
    )


def test_update_meter_image_url(client, db):
    t = _admin(client)
    _unlock_pro(db)
    mid = client.post(
        "/api/v1/meters", headers=_h(t), json={"name": "M"}
    ).json()["id"]
    r = client.patch(
        f"/api/v1/meters/{mid}", headers=_h(t), json={"image_url": "https://img/y.png"}
    )
    assert r.status_code == 200
    assert r.json()["image_url"] == "https://img/y.png"


def test_set_and_read_back_user_ids(client, db):
    t = _admin(client)
    _unlock_pro(db)
    u1 = _make_user(client, t, email="u1@acme.com")
    u2 = _make_user(client, t, email="u2@acme.com")
    mid = client.post(
        "/api/v1/meters", headers=_h(t), json={"name": "M", "user_ids": [u1, u2]}
    ).json()["id"]
    got = client.get(f"/api/v1/meters/{mid}", headers=_h(t)).json()
    assert sorted(got["user_ids"]) == sorted([u1, u2])
    # 出现在列表端点
    listed = client.get("/api/v1/meters", headers=_h(t)).json()
    row = next(m for m in listed if m["id"] == mid)
    assert sorted(row["user_ids"]) == sorted([u1, u2])


def test_update_user_ids_full_replace(client, db):
    t = _admin(client)
    _unlock_pro(db)
    u1 = _make_user(client, t, email="u1@acme.com")
    u2 = _make_user(client, t, email="u2@acme.com")
    mid = client.post(
        "/api/v1/meters", headers=_h(t), json={"name": "M", "user_ids": [u1]}
    ).json()["id"]
    r = client.patch(f"/api/v1/meters/{mid}", headers=_h(t), json={"user_ids": [u2]})
    assert r.status_code == 200
    assert r.json()["user_ids"] == [u2]


def test_user_ids_none_keeps_existing(client, db):
    t = _admin(client)
    _unlock_pro(db)
    u1 = _make_user(client, t, email="u1@acme.com")
    mid = client.post(
        "/api/v1/meters", headers=_h(t), json={"name": "M", "user_ids": [u1]}
    ).json()["id"]
    # 不传 user_ids -> 不改
    r = client.patch(f"/api/v1/meters/{mid}", headers=_h(t), json={"name": "M2"})
    assert r.status_code == 200
    assert r.json()["user_ids"] == [u1]


def test_user_ids_empty_clears(client, db):
    t = _admin(client)
    _unlock_pro(db)
    u1 = _make_user(client, t, email="u1@acme.com")
    mid = client.post(
        "/api/v1/meters", headers=_h(t), json={"name": "M", "user_ids": [u1]}
    ).json()["id"]
    r = client.patch(f"/api/v1/meters/{mid}", headers=_h(t), json={"user_ids": []})
    assert r.status_code == 200
    assert r.json()["user_ids"] == []


def test_cross_tenant_user_rejected_on_create(client, db):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Globex", email="b@globex.com")
    _unlock_pro(db)
    foreign = _make_user(client, tb, email="b-user@globex.com")
    r = client.post(
        "/api/v1/meters", headers=_h(ta), json={"name": "M", "user_ids": [foreign]}
    )
    assert r.status_code == 404, r.text


def test_cross_tenant_user_rejected_on_update(client, db):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Globex", email="b@globex.com")
    _unlock_pro(db)
    foreign = _make_user(client, tb, email="b-user@globex.com")
    mid = client.post("/api/v1/meters", headers=_h(ta), json={"name": "M"}).json()["id"]
    r = client.patch(
        f"/api/v1/meters/{mid}", headers=_h(ta), json={"user_ids": [foreign]}
    )
    assert r.status_code == 404
