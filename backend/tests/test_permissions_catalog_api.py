"""权限目录端点：ROLE_VIEW 鉴权 + 分组结构 + 覆盖 ALL_PERMISSIONS。"""

from __future__ import annotations

from app.permissions import ALL_PERMISSIONS


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def test_requires_auth(client):
    assert client.get("/api/v1/permissions").status_code == 401


def test_forbidden_without_role_view(client):
    """有登录态但缺 ROLE_VIEW 的用户访问目录端点应 403。"""
    admin = _admin(client)
    h = {"Authorization": f"Bearer {admin}"}
    # 自定义角色仅含 user.view，不含 role.view
    role_id = client.post(
        "/api/v1/roles",
        headers=h,
        json={"code": "noroleview", "name": "无角色权限", "permissions": ["user.view"]},
    ).json()["id"]
    client.post(
        "/api/v1/users",
        headers=h,
        json={"email": "low@acme.com", "password": "secret123", "name": "Low"},
    )
    uid = next(
        u for u in client.get("/api/v1/users", headers=h).json() if u["email"] == "low@acme.com"
    )["id"]
    client.patch(f"/api/v1/users/{uid}", headers=h, json={"role_id": role_id})
    low = client.post(
        "/api/v1/auth/login",
        json={"email": "low@acme.com", "password": "secret123", "company_slug": "acme"},
    ).json()["access_token"]
    r = client.get("/api/v1/permissions", headers={"Authorization": f"Bearer {low}"})
    assert r.status_code == 403, r.text


def test_catalog_covers_all_permissions(client):
    t = _admin(client)
    body = client.get("/api/v1/permissions", headers={"Authorization": f"Bearer {t}"}).json()
    codes = {p["code"] for g in body for p in g["permissions"]}
    assert codes == set(ALL_PERMISSIONS)
    assert all("group" in g and isinstance(g["permissions"], list) for g in body)
    # 每项有中文 label
    assert all(p["label"] for g in body for p in g["permissions"])
