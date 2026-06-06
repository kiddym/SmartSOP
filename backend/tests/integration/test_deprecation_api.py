"""资产折旧 API 集成测试：PUT upsert / GET 读回 / current_value 直线法 / DELETE /
跨租户 404 / 权限（无 asset.edit 不能 PUT）。"""

from __future__ import annotations

from datetime import date


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _asset(client, token, name="泵1"):
    return client.post("/api/v1/assets", headers=_h(token), json={"name": name}).json()["id"]


def _viewer_token(client, admin_token):
    """viewer 内置角色含 asset.view 但不含 asset.edit。"""
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


def test_put_creates_and_get_reads_back(client):
    t = _admin(client)
    aid = _asset(client, t)
    assert client.get(f"/api/v1/assets/{aid}/deprecation", headers=_h(t)).json() is None
    r = client.put(
        f"/api/v1/assets/{aid}/deprecation",
        headers=_h(t),
        json={
            "purchase_price": "10000.00",
            "purchase_date": "2020-01-01",
            "residual_value": "1000.00",
            "useful_life_years": 5,
            "rate": "0.1800",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["asset_id"] == aid
    assert body["useful_life_years"] == 5
    got = client.get(f"/api/v1/assets/{aid}/deprecation", headers=_h(t)).json()
    assert got["purchase_price"] == "10000.00"
    assert got["residual_value"] == "1000.00"
    assert got["rate"] == "0.1800"


def test_put_updates_existing(client):
    t = _admin(client)
    aid = _asset(client, t)
    client.put(
        f"/api/v1/assets/{aid}/deprecation",
        headers=_h(t),
        json={"purchase_price": "5000.00", "useful_life_years": 10},
    )
    r = client.put(
        f"/api/v1/assets/{aid}/deprecation",
        headers=_h(t),
        json={"purchase_price": "8000.00", "useful_life_years": 8},
    )
    assert r.status_code == 200
    got = client.get(f"/api/v1/assets/{aid}/deprecation", headers=_h(t)).json()
    assert got["purchase_price"] == "8000.00"
    assert got["useful_life_years"] == 8


def test_current_value_straight_line(client):
    t = _admin(client)
    aid = _asset(client, t)
    # 购置价 10000、残值 1000、年限 5 → 年折旧 1800。
    # 购置日设为恰好 3 整年前 → current = 10000 - 1800*3 = 4600.00。
    three_years_ago = date.today().replace(year=date.today().year - 3).isoformat()
    r = client.put(
        f"/api/v1/assets/{aid}/deprecation",
        headers=_h(t),
        json={
            "purchase_price": "10000.00",
            "purchase_date": three_years_ago,
            "residual_value": "1000.00",
            "useful_life_years": 5,
        },
    )
    assert r.json()["current_value"] == "4600.00"


def test_current_value_floors_at_residual(client):
    t = _admin(client)
    aid = _asset(client, t)
    # 已过年数远超年限 → current 不低于残值。
    ten_years_ago = date.today().replace(year=date.today().year - 10).isoformat()
    r = client.put(
        f"/api/v1/assets/{aid}/deprecation",
        headers=_h(t),
        json={
            "purchase_price": "10000.00",
            "purchase_date": ten_years_ago,
            "residual_value": "1000.00",
            "useful_life_years": 5,
        },
    )
    assert r.json()["current_value"] == "1000.00"


def test_current_value_null_when_fields_missing(client):
    t = _admin(client)
    aid = _asset(client, t)
    r = client.put(
        f"/api/v1/assets/{aid}/deprecation",
        headers=_h(t),
        json={"purchase_price": "10000.00"},  # 缺年限/残值/购置日
    )
    assert r.json()["current_value"] is None


def test_delete(client):
    t = _admin(client)
    aid = _asset(client, t)
    client.put(
        f"/api/v1/assets/{aid}/deprecation",
        headers=_h(t),
        json={"purchase_price": "5000.00"},
    )
    assert client.delete(f"/api/v1/assets/{aid}/deprecation", headers=_h(t)).status_code == 204
    assert client.get(f"/api/v1/assets/{aid}/deprecation", headers=_h(t)).json() is None
    # 再删不存在 → 404
    assert client.delete(f"/api/v1/assets/{aid}/deprecation", headers=_h(t)).status_code == 404


def test_requires_auth(client):
    t = _admin(client)
    aid = _asset(client, t)
    assert client.get(f"/api/v1/assets/{aid}/deprecation").status_code == 401


def test_cross_tenant_404(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Globex", email="b@globex.com")
    aid_b = _asset(client, tb, name="B泵")
    # A 访问 B 的资产折旧 → 资产不属 A → 404
    assert client.get(f"/api/v1/assets/{aid_b}/deprecation", headers=_h(ta)).status_code == 404
    assert (
        client.put(
            f"/api/v1/assets/{aid_b}/deprecation",
            headers=_h(ta),
            json={"purchase_price": "1.00"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/assets/{aid_b}/deprecation", headers=_h(ta)).status_code == 404


def test_viewer_can_get_but_not_put(client):
    admin = _admin(client)
    aid = _asset(client, admin)
    viewer = _viewer_token(client, admin)
    assert client.get(f"/api/v1/assets/{aid}/deprecation", headers=_h(viewer)).status_code == 200
    assert (
        client.put(
            f"/api/v1/assets/{aid}/deprecation",
            headers=_h(viewer),
            json={"purchase_price": "1.00"},
        ).status_code
        == 403
    )
