"""维修请求 API 集成测试（Phase 2A）。"""
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


def _seed_user(db, *, slug="acme", perms=None):
    company = Company(name=slug.title(), slug=slug)
    db.add(company)
    db.commit()
    role = Role(
        company_id=company.id, code="r-" + slug, name="R",
        permissions=perms if perms is not None else [],
    )
    db.add(role)
    db.commit()
    user = User(
        company_id=company.id, email=f"u@{slug}.com", name="U",
        password_hash="x", role_id=role.id,
    )
    db.add(user)
    db.commit()
    return company, user


def _token(user):
    return auth_service.create_access_token(user)


def _auth(user):
    return {"Authorization": f"Bearer {_token(user)}"}


_ALL = list(permissions.ALL_PERMISSIONS)


def test_create_and_get_request(client, db):
    _, user = _seed_user(db, perms=_ALL)
    resp = client.post("/api/v1/requests", json={"title": "漏水"}, headers=_auth(user))
    assert resp.status_code == 201
    rid = resp.json()["id"]
    assert resp.json()["custom_id"] == "RQ000001"
    got = client.get(f"/api/v1/requests/{rid}", headers=_auth(user))
    assert got.status_code == 200
    assert got.json()["status"] == "PENDING"


def test_approve_generates_work_order(client, db):
    _, user = _seed_user(db, perms=_ALL)
    rid = client.post("/api/v1/requests", json={"title": "t"},
                      headers=_auth(user)).json()["id"]
    resp = client.post(f"/api/v1/requests/{rid}/approve", json={"note": "ok"},
                       headers=_auth(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "APPROVED"
    assert body["work_order_id"] is not None


def test_pending_list_excludes_resolved(client, db):
    _, user = _seed_user(db, perms=_ALL)
    a = client.post("/api/v1/requests", json={"title": "a"},
                    headers=_auth(user)).json()["id"]
    b = client.post("/api/v1/requests", json={"title": "b"},
                    headers=_auth(user)).json()["id"]
    client.post(f"/api/v1/requests/{b}/cancel", json={"reason": "x"}, headers=_auth(user))
    pending = client.get("/api/v1/requests/pending", headers=_auth(user))
    ids = {r["id"] for r in pending.json()}
    assert a in ids and b not in ids


def test_requester_cannot_approve(client, db):
    _, user = _seed_user(db, perms=["request.view", "request.create"])
    rid = client.post("/api/v1/requests", json={"title": "t"},
                      headers=_auth(user)).json()["id"]
    resp = client.post(f"/api/v1/requests/{rid}/approve", json={}, headers=_auth(user))
    assert resp.status_code == 403


def test_comment_and_activities(client, db):
    _, user = _seed_user(db, perms=_ALL)
    rid = client.post("/api/v1/requests", json={"title": "t"},
                      headers=_auth(user)).json()["id"]
    client.post(f"/api/v1/requests/{rid}/activities", json={"comment": "hi"},
                headers=_auth(user))
    acts = client.get(f"/api/v1/requests/{rid}/activities", headers=_auth(user))
    assert any(a["activity_type"] == "COMMENT" for a in acts.json())
