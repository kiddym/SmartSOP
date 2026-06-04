"""Part↔PM 关联：内嵌 pm_ids + 同步 + 跨租户校验。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("_enterprise_default")


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _pm(client, t, title="月度巡检"):
    return client.post(
        "/api/v1/preventive-maintenances",
        headers=_h(t),
        json={
            "title": title,
            "start_date": "2026-01-01",
            "frequency_unit": "MONTH",
            "frequency_value": 1,
        },
    ).json()["id"]


def _part(client, t, name="轴承", **extra):
    return client.post("/api/v1/parts", headers=_h(t), json={"name": name, **extra})


def test_create_with_pms(client):
    t = _admin(client)
    pm = _pm(client, t)
    r = _part(client, t, pm_ids=[pm])
    assert r.status_code == 201, r.text
    assert r.json()["pm_ids"] == [pm]


def test_update_replaces_pms(client):
    t = _admin(client)
    pm1, pm2 = _pm(client, t, "巡检A"), _pm(client, t, "巡检B")
    pid = _part(client, t, pm_ids=[pm1]).json()["id"]
    r = client.patch(f"/api/v1/parts/{pid}", headers=_h(t), json={"pm_ids": [pm2]})
    assert r.json()["pm_ids"] == [pm2]
    r2 = client.patch(f"/api/v1/parts/{pid}", headers=_h(t), json={"pm_ids": []})
    assert r2.json()["pm_ids"] == []


def test_cross_tenant_pm_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    pm_a = _pm(client, ta, "A巡检")
    r = _part(client, tb, pm_ids=[pm_a])
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "PREVENTIVE_MAINTENANCE_NOT_FOUND"
