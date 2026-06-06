"""读数 PATCH/DELETE + 软频率校验（I 尾项第 1 批）。"""

from __future__ import annotations

from sqlalchemy import select

from app.models.company import Company


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _unlock_pro(db):
    for c in db.execute(select(Company)).scalars().all():
        c.plan = "pro"
        c.subscription_status = "active"
    db.commit()


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _meter(client, token, **kw):
    body = {"name": "温度表", "unit": "℃"}
    body.update(kw)
    return client.post("/api/v1/meters", json=body, headers=_h(token))


def test_patch_reading_updates_value(client, db):
    t = _admin(client)
    _unlock_pro(db)
    mid = _meter(client, t).json()["id"]
    rid = client.post(f"/api/v1/meters/{mid}/readings", json={"value": "10"}, headers=_h(t)).json()[
        "reading"
    ]["id"]
    r = client.patch(f"/api/v1/meters/{mid}/readings/{rid}", json={"value": "42.5"}, headers=_h(t))
    assert r.status_code == 200, r.text
    assert float(r.json()["value"]) == 42.5


def test_delete_reading_204(client, db):
    t = _admin(client)
    _unlock_pro(db)
    mid = _meter(client, t).json()["id"]
    rid = client.post(f"/api/v1/meters/{mid}/readings", json={"value": "10"}, headers=_h(t)).json()[
        "reading"
    ]["id"]
    assert client.delete(f"/api/v1/meters/{mid}/readings/{rid}", headers=_h(t)).status_code == 204
    assert len(client.get(f"/api/v1/meters/{mid}/readings", headers=_h(t)).json()) == 0


def test_patch_reading_cross_tenant_404(client, db):
    a = _admin(client)
    _unlock_pro(db)
    mid = _meter(client, a).json()["id"]
    rid = client.post(f"/api/v1/meters/{mid}/readings", json={"value": "10"}, headers=_h(a)).json()[
        "reading"
    ]["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    _unlock_pro(db)
    assert (
        client.patch(
            f"/api/v1/meters/{mid}/readings/{rid}", json={"value": "1"}, headers=_h(b)
        ).status_code
        == 404
    )


def test_frequency_rejects_too_frequent(client, db):
    t = _admin(client)
    _unlock_pro(db)
    # update_frequency_days=7：两条紧挨的读数应被拒
    mid = _meter(client, t, update_frequency_days=7).json()["id"]
    r1 = client.post(
        f"/api/v1/meters/{mid}/readings",
        json={"value": "10", "reading_at": "2026-06-01T00:00:00"},
        headers=_h(t),
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        f"/api/v1/meters/{mid}/readings",
        json={"value": "11", "reading_at": "2026-06-03T00:00:00"},
        headers=_h(t),
    )
    assert r2.status_code == 422, r2.text
    assert r2.json()["detail"]["code"] == "READING_FREQUENCY_NOT_RESPECTED"
    # 满足间隔则放行
    r3 = client.post(
        f"/api/v1/meters/{mid}/readings",
        json={"value": "12", "reading_at": "2026-06-10T00:00:00"},
        headers=_h(t),
    )
    assert r3.status_code == 201, r3.text


def test_frequency_unset_does_not_validate(client, db):
    t = _admin(client)
    _unlock_pro(db)
    # 无 update_frequency_days：任意密集读数均放行（既有行为不破）
    mid = _meter(client, t).json()["id"]
    for v in ("1", "2", "3"):
        r = client.post(f"/api/v1/meters/{mid}/readings", json={"value": v}, headers=_h(t))
        assert r.status_code == 201, r.text
    assert len(client.get(f"/api/v1/meters/{mid}/readings", headers=_h(t)).json()) == 3
