"""Phase 2A 跨租户隔离验收（e2e，经中间件按 token 驱动租户上下文）。

全程经 API（register）建立两个租户的认证主体，使用 conftest 的 `client` fixture。
"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company, email):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def test_requests_isolated_across_tenants(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Globex", email="b@globex.com")
    rid_b = client.post("/api/v1/requests", json={"title": "B单"}, headers=_h(tb)).json()["id"]

    # A 读/改/删/审批/拒绝/取消 B 的请求 → 404
    assert client.get(f"/api/v1/requests/{rid_b}", headers=_h(ta)).status_code == 404
    assert (
        client.patch(f"/api/v1/requests/{rid_b}", json={"title": "x"}, headers=_h(ta)).status_code
        == 404
    )
    assert client.delete(f"/api/v1/requests/{rid_b}", headers=_h(ta)).status_code == 404
    assert (
        client.post(f"/api/v1/requests/{rid_b}/approve", json={}, headers=_h(ta)).status_code == 404
    )
    assert (
        client.post(
            f"/api/v1/requests/{rid_b}/reject", json={"reason": "x"}, headers=_h(ta)
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/requests/{rid_b}/cancel", json={"reason": "x"}, headers=_h(ta)
        ).status_code
        == 404
    )

    # A 的列表不含 B
    client.post("/api/v1/requests", json={"title": "A单"}, headers=_h(ta))
    ids = {r["id"] for r in client.get("/api/v1/requests", headers=_h(ta)).json()}
    assert rid_b not in ids


def test_custom_id_per_tenant_independent(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Globex", email="b@globex.com")
    a = client.post("/api/v1/requests", json={"title": "x"}, headers=_h(ta)).json()
    b = client.post("/api/v1/requests", json={"title": "y"}, headers=_h(tb)).json()
    assert a["custom_id"] == "RQ000001" and b["custom_id"] == "RQ000001"
