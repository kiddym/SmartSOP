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


def test_catalog_covers_all_permissions(client):
    t = _admin(client)
    body = client.get("/api/v1/permissions", headers={"Authorization": f"Bearer {t}"}).json()
    codes = {p["code"] for g in body for p in g["permissions"]}
    assert codes == set(ALL_PERMISSIONS)
    assert all("group" in g and isinstance(g["permissions"], list) for g in body)
    # 每项有中文 label
    assert all(p["label"] for g in body for p in g["permissions"])
