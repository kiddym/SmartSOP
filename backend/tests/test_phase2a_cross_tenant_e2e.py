"""Phase 2A 跨租户隔离验收（e2e，经中间件按 token 驱动租户上下文）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import permissions
from app.main import app
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.services import auth_service


@pytest.fixture
def client():
    return TestClient(app)


def _seed(db, slug):
    company = Company(name=slug.title(), slug=slug)
    db.add(company)
    db.commit()
    role = Role(company_id=company.id, code="r-" + slug, name="R",
                permissions=list(permissions.ALL_PERMISSIONS))
    db.add(role)
    db.commit()
    user = User(company_id=company.id, email=f"u@{slug}.com", name="U",
                password_hash="x", role_id=role.id)
    db.add(user)
    db.commit()
    return company, user


def _auth(user):
    return {"Authorization": f"Bearer {auth_service.create_access_token(user)}"}


def test_requests_isolated_across_tenants(client, db):
    _, ua = _seed(db, "acme")
    _, ub = _seed(db, "globex")
    rid_b = client.post("/api/v1/requests", json={"title": "B单"},
                        headers=_auth(ub)).json()["id"]

    # A 读/改/删/审批/拒绝/取消 B 的请求 → 404
    assert client.get(f"/api/v1/requests/{rid_b}", headers=_auth(ua)).status_code == 404
    assert client.patch(f"/api/v1/requests/{rid_b}", json={"title": "x"},
                        headers=_auth(ua)).status_code == 404
    assert client.delete(f"/api/v1/requests/{rid_b}", headers=_auth(ua)).status_code == 404
    assert client.post(f"/api/v1/requests/{rid_b}/approve", json={},
                       headers=_auth(ua)).status_code == 404
    assert client.post(f"/api/v1/requests/{rid_b}/reject", json={"reason": "x"},
                       headers=_auth(ua)).status_code == 404
    assert client.post(f"/api/v1/requests/{rid_b}/cancel", json={"reason": "x"},
                       headers=_auth(ua)).status_code == 404

    # A 的列表不含 B
    client.post("/api/v1/requests", json={"title": "A单"}, headers=_auth(ua))
    ids = {r["id"] for r in client.get("/api/v1/requests", headers=_auth(ua)).json()}
    assert rid_b not in ids


def test_custom_id_per_tenant_independent(client, db):
    _, ua = _seed(db, "acme")
    _, ub = _seed(db, "globex")
    a = client.post("/api/v1/requests", json={"title": "x"}, headers=_auth(ua)).json()
    b = client.post("/api/v1/requests", json={"title": "y"}, headers=_auth(ub)).json()
    assert a["custom_id"] == "RQ000001" and b["custom_id"] == "RQ000001"
