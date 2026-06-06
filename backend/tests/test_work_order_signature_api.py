"""工单完成签名（required_signature / signature_url）（I 尾项第 1 批）。"""

from __future__ import annotations


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company: str = "Acme", email: str = "admin@acme.com") -> str:
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _wo(client, t, **kw):
    body = {"title": "检修"}
    body.update(kw)
    return client.post("/api/v1/work-orders", json=body, headers=_h(t)).json()


def _start(client, t, wo_id):
    r = client.post(
        f"/api/v1/work-orders/{wo_id}/transition",
        json={"to_status": "IN_PROGRESS"},
        headers=_h(t),
    )
    assert r.status_code == 200, r.text


def _complete(client, t, wo_id, **payload):
    body = {"to_status": "COMPLETE"}
    body.update(payload)
    return client.post(f"/api/v1/work-orders/{wo_id}/transition", json=body, headers=_h(t))


def test_required_signature_blocks_complete_without_signature(client):
    t = _admin(client)
    wo = _wo(client, t, required_signature=True)
    assert wo["required_signature"] is True
    _start(client, t, wo["id"])
    r = _complete(client, t, wo["id"])
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "SIGNATURE_REQUIRED"


def test_required_signature_completes_with_signature(client):
    t = _admin(client)
    wo = _wo(client, t, required_signature=True)
    _start(client, t, wo["id"])
    r = _complete(client, t, wo["id"], signature_url="https://x/sig.png")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETE"
    assert r.json()["signature_url"] == "https://x/sig.png"


def test_non_required_completes_normally(client):
    t = _admin(client)
    wo = _wo(client, t)
    assert wo["required_signature"] is False
    _start(client, t, wo["id"])
    r = _complete(client, t, wo["id"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETE"


def test_update_sets_required_signature(client):
    t = _admin(client)
    wo = _wo(client, t)
    r = client.patch(
        f"/api/v1/work-orders/{wo['id']}",
        json={"required_signature": True},
        headers=_h(t),
    )
    assert r.status_code == 200, r.text
    assert r.json()["required_signature"] is True
