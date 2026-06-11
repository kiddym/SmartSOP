"""GET /settings 应返回 auto_archive_days（审计 #9）。"""
from __future__ import annotations


def _register(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def test_settings_includes_auto_archive_days(client):
    tok = _register(client)
    r = client.get("/api/v1/settings/current", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "auto_archive_days" in body
    assert isinstance(body["auto_archive_days"], int)
