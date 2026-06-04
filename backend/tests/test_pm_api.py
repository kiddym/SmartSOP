"""PM API 集成测试（Phase 2B）。经 auth API 建主体，不手工 db.add(User)。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("_enterprise_default")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


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


def _create_body(**kw):
    body = {
        "title": "月检",
        "start_date": "2026-06-01",
        "frequency_unit": "MONTH",
        "frequency_value": 1,
    }
    body.update(kw)
    return body


def test_create_and_get_pm(client):
    t = _admin(client)
    r = client.post("/api/v1/preventive-maintenances", json=_create_body(), headers=_h(t))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["custom_id"] == "PM000001"
    assert r.json()["next_due_date"] == "2026-06-01"
    got = client.get(f"/api/v1/preventive-maintenances/{pid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["is_enabled"] is True


def test_enable_disable(client):
    t = _admin(client)
    pid = client.post("/api/v1/preventive-maintenances", json=_create_body(), headers=_h(t)).json()[
        "id"
    ]
    assert (
        client.post(f"/api/v1/preventive-maintenances/{pid}/disable", headers=_h(t)).json()[
            "is_enabled"
        ]
        is False
    )
    assert (
        client.post(f"/api/v1/preventive-maintenances/{pid}/enable", headers=_h(t)).json()[
            "is_enabled"
        ]
        is True
    )


def test_manual_generate_returns_work_order(client):
    t = _admin(client)
    # start_date 设过去 -> 到期；但手动 generate 不校验到期亦可
    pid = client.post(
        "/api/v1/preventive-maintenances", json=_create_body(start_date="2026-01-01"), headers=_h(t)
    ).json()["id"]
    r = client.post(f"/api/v1/preventive-maintenances/{pid}/generate", headers=_h(t))
    assert r.status_code == 201, r.text
    assert r.json()["custom_id"].startswith("WO")


def test_manual_generate_response_includes_presets(client):
    # /generate 响应须经 to_read 填充 assignee_ids/team_ids（防回归：勿返回裸 ORM）
    t = _admin(client)
    pid = client.post(
        "/api/v1/preventive-maintenances",
        json=_create_body(start_date="2026-01-01", assignee_ids=["u-1"], team_ids=["t-1"]),
        headers=_h(t),
    ).json()["id"]
    r = client.post(f"/api/v1/preventive-maintenances/{pid}/generate", headers=_h(t))
    assert r.status_code == 201, r.text
    assert r.json()["assignee_ids"] == ["u-1"]
    assert r.json()["team_ids"] == ["t-1"]


def test_activities_and_comment(client):
    t = _admin(client)
    pid = client.post("/api/v1/preventive-maintenances", json=_create_body(), headers=_h(t)).json()[
        "id"
    ]
    client.post(
        f"/api/v1/preventive-maintenances/{pid}/comments", json={"comment": "hi"}, headers=_h(t)
    )
    acts = client.get(f"/api/v1/preventive-maintenances/{pid}/activities", headers=_h(t))
    assert any(a["activity_type"] == "COMMENT" for a in acts.json())


def test_technician_cannot_create(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    r = client.post("/api/v1/preventive-maintenances", json=_create_body(), headers=_h(tech))
    assert r.status_code == 403


def test_tenant_isolation(client):
    a = _admin(client)
    pid = client.post("/api/v1/preventive-maintenances", json=_create_body(), headers=_h(a)).json()[
        "id"
    ]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/preventive-maintenances/{pid}", headers=_h(b)).status_code == 404
