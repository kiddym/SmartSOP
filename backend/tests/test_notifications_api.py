"""站内通知 API（Phase 5A）：鉴权/分页/未读数/标记已读/只见自己/跨租户。"""

from __future__ import annotations

import json

from sqlalchemy import select

from app.models.company import Company
from app.models.notification import Notification


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def _me_id(client, token):
    return client.get("/api/v1/auth/me", headers=_h(token)).json()["id"]


def _seed(db, *, company_id, recipient, type="WO_ASSIGNED", is_read=False):
    n = Notification(
        company_id=company_id,
        recipient_user_id=recipient,
        type=type,
        entity_type="work_order",
        entity_id="wo-1",
        params=json.dumps({"custom_id": "WO1"}),
        is_read=is_read,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def test_requires_auth(client):
    assert client.get("/api/v1/notifications").status_code == 401


def test_feed_returns_own_paginated(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    for _i in range(3):
        _seed(db, company_id=co, recipient=me)
    body = client.get("/api/v1/notifications?page=1&page_size=2", headers=_h(t)).json()
    assert body["total"] == 3 and len(body["items"]) == 2
    assert body["page"] == 1 and body["page_size"] == 2 and body["total_pages"] == 2
    assert body["items"][0]["params"]["custom_id"] == "WO1"


def test_feed_only_sees_own(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    _seed(db, company_id=co, recipient=me)
    _seed(db, company_id=co, recipient="someone-else")
    body = client.get("/api/v1/notifications", headers=_h(t)).json()
    assert body["total"] == 1 and body["items"][0]["params"]["custom_id"] == "WO1"


def test_feed_filter_is_read(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    _seed(db, company_id=co, recipient=me, is_read=False)
    _seed(db, company_id=co, recipient=me, is_read=True)
    body = client.get("/api/v1/notifications?is_read=false", headers=_h(t)).json()
    assert body["total"] == 1


def test_unread_count(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    _seed(db, company_id=co, recipient=me, is_read=False)
    _seed(db, company_id=co, recipient=me, is_read=False)
    _seed(db, company_id=co, recipient=me, is_read=True)
    assert client.get("/api/v1/notifications/unread-count", headers=_h(t)).json()["count"] == 2


def test_mark_one_read(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    n = _seed(db, company_id=co, recipient=me)
    assert client.post(f"/api/v1/notifications/{n.id}/read", headers=_h(t)).status_code == 200
    assert client.get("/api/v1/notifications/unread-count", headers=_h(t)).json()["count"] == 0


def test_mark_one_read_not_owner_404(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    n = _seed(db, company_id=co, recipient="not-me")
    assert client.post(f"/api/v1/notifications/{n.id}/read", headers=_h(t)).status_code == 404


def test_mark_all_read(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    _seed(db, company_id=co, recipient=me)
    _seed(db, company_id=co, recipient=me)
    r = client.post("/api/v1/notifications/read-all", headers=_h(t)).json()
    assert r["updated"] == 2
    assert client.get("/api/v1/notifications/unread-count", headers=_h(t)).json()["count"] == 0


def test_tenant_isolation(client, db):
    ta = _admin(client, company="Acme", email="a@acme.com")
    _admin(client, company="Beta", email="b@beta.com")
    co_b = _company_id(db, "beta")
    me_a = _me_id(client, ta)
    # 给 B 公司插一条 recipient 恰为 A 用户 id（同 id 跨租户也不可见）
    _seed(db, company_id=co_b, recipient=me_a)
    assert client.get("/api/v1/notifications", headers=_h(ta)).json()["total"] == 0
