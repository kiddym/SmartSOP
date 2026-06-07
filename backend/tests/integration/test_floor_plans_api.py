"""位置平面图 API 集成测试：POST 建多张 / GET 列表 / PATCH 改 / DELETE /
跨租户 404 / 权限（无 location.edit 不能写）。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _location(client, token, name="厂区A"):
    return client.post("/api/v1/locations", headers=_h(token), json={"name": name}).json()["id"]


def _viewer_token(client, admin_token):
    """viewer 内置角色含 location.view 但不含 location.edit。"""
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "viewer")
    client.post(
        "/api/v1/users",
        headers=_h(admin_token),
        json={"email": "v@acme.com", "password": "secret123", "name": "V", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "v@acme.com", "password": "secret123"},
    ).json()["access_token"]


def _base(loc_id):
    return f"/api/v1/locations/{loc_id}/floor-plans"


def test_create_multiple_and_list(client):
    t = _admin(client)
    loc = _location(client, t)
    assert client.get(_base(loc), headers=_h(t)).json() == []
    r1 = client.post(
        _base(loc),
        headers=_h(t),
        json={"name": "一层", "image_url": "https://x/1.png", "area": "1200.50"},
    )
    assert r1.status_code == 201, r1.text
    body = r1.json()
    assert body["name"] == "一层"
    assert body["location_id"] == loc
    assert body["image_url"] == "https://x/1.png"
    assert body["area"] == "1200.50"
    r2 = client.post(_base(loc), headers=_h(t), json={"name": "二层"})
    assert r2.status_code == 201
    assert r2.json()["image_url"] is None
    assert r2.json()["area"] is None
    rows = client.get(_base(loc), headers=_h(t)).json()
    assert [x["name"] for x in rows] == ["一层", "二层"]


def test_patch_updates(client):
    t = _admin(client)
    loc = _location(client, t)
    fid = client.post(_base(loc), headers=_h(t), json={"name": "旧", "area": "100.00"}).json()["id"]
    r = client.patch(
        f"{_base(loc)}/{fid}",
        headers=_h(t),
        json={"name": "新", "area": "250.75"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "新"
    assert r.json()["area"] == "250.75"


def test_patch_partial_keeps_other_fields(client):
    t = _admin(client)
    loc = _location(client, t)
    fid = client.post(
        _base(loc),
        headers=_h(t),
        json={"name": "保留", "image_url": "https://x/a.png", "area": "9.00"},
    ).json()["id"]
    # 仅改 name，image_url/area 应保持。
    r = client.patch(f"{_base(loc)}/{fid}", headers=_h(t), json={"name": "改名"})
    assert r.status_code == 200
    assert r.json()["name"] == "改名"
    assert r.json()["image_url"] == "https://x/a.png"
    assert r.json()["area"] == "9.00"


def test_delete(client):
    t = _admin(client)
    loc = _location(client, t)
    fid = client.post(_base(loc), headers=_h(t), json={"name": "待删"}).json()["id"]
    assert client.delete(f"{_base(loc)}/{fid}", headers=_h(t)).status_code == 204
    assert client.get(_base(loc), headers=_h(t)).json() == []
    # 再删不存在 → 404
    assert client.delete(f"{_base(loc)}/{fid}", headers=_h(t)).status_code == 404


def test_requires_auth(client):
    t = _admin(client)
    loc = _location(client, t)
    assert client.get(_base(loc)).status_code == 401


def test_cross_tenant_404(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Globex", email="b@globex.com")
    loc_b = _location(client, tb, name="B厂区")
    fid_b = client.post(_base(loc_b), headers=_h(tb), json={"name": "B一层"}).json()["id"]
    # A 访问 B 的位置平面图 → 位置不属 A → 404
    assert client.get(_base(loc_b), headers=_h(ta)).status_code == 404
    assert client.post(_base(loc_b), headers=_h(ta), json={"name": "x"}).status_code == 404
    assert (
        client.patch(f"{_base(loc_b)}/{fid_b}", headers=_h(ta), json={"name": "x"}).status_code
        == 404
    )
    assert client.delete(f"{_base(loc_b)}/{fid_b}", headers=_h(ta)).status_code == 404


def test_floor_plan_not_owned_by_location_404(client):
    t = _admin(client)
    loc1 = _location(client, t, name="厂区1")
    loc2 = _location(client, t, name="厂区2")
    fid = client.post(_base(loc1), headers=_h(t), json={"name": "L1图"}).json()["id"]
    # 同租户但平面图不属 loc2 → 404
    assert (
        client.patch(f"{_base(loc2)}/{fid}", headers=_h(t), json={"name": "x"}).status_code == 404
    )
    assert client.delete(f"{_base(loc2)}/{fid}", headers=_h(t)).status_code == 404


def test_viewer_can_list_but_not_write(client):
    admin = _admin(client)
    loc = _location(client, admin)
    fid = client.post(_base(loc), headers=_h(admin), json={"name": "图"}).json()["id"]
    viewer = _viewer_token(client, admin)
    assert client.get(_base(loc), headers=_h(viewer)).status_code == 200
    assert client.post(_base(loc), headers=_h(viewer), json={"name": "x"}).status_code == 403
    assert (
        client.patch(f"{_base(loc)}/{fid}", headers=_h(viewer), json={"name": "x"}).status_code
        == 403
    )
    assert client.delete(f"{_base(loc)}/{fid}", headers=_h(viewer)).status_code == 403
