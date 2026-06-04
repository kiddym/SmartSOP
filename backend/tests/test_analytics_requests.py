"""/analytics/requests：总览 + 周期 + 收到vs解决 + 转化。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.request import Request
from app.models.request_status import RequestStatus

pytestmark = pytest.mark.usefixtures("_enterprise_default")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_request_analytics_shape(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    now = datetime.utcnow()
    db.add(
        Request(
            custom_id="RQ1",
            title="r1",
            status=RequestStatus.APPROVED,
            created_at=now - timedelta(hours=2),
            resolved_at=now,
            work_order_id="WO-x",
            company_id=co,
        )
    )
    db.add(
        Request(
            custom_id="RQ2", title="r2", status=RequestStatus.PENDING, created_at=now, company_id=co
        )
    )
    db.commit()
    body = client.get("/api/v1/analytics/requests", headers=_h(t)).json()
    assert body["total"] == 2
    assert body["by_status"]["APPROVED"] == 1 and body["by_status"]["PENDING"] == 1
    assert body["received"] == 2
    assert body["resolved"] == 1
    assert body["converted"] == 1
    assert body["avg_resolution_cycle_hours"] == 2.0


def test_request_analytics_tenant_isolation(client, db):
    """B 公司的请求不应出现在 A 公司的统计里。"""
    ta = _admin(client)
    co_a = _company_id(db, "acme")
    tb = _admin(client, company="Beta", email="b@beta.com")
    co_b = _company_id(db, "beta")
    now = datetime.utcnow()
    db.add(
        Request(
            custom_id="RA1",
            title="ra",
            status=RequestStatus.PENDING,
            created_at=now,
            company_id=co_a,
        )
    )
    db.add(
        Request(
            custom_id="RB1",
            title="rb",
            status=RequestStatus.PENDING,
            created_at=now,
            company_id=co_b,
        )
    )
    db.add(
        Request(
            custom_id="RB2",
            title="rb2",
            status=RequestStatus.PENDING,
            created_at=now,
            company_id=co_b,
        )
    )
    db.commit()
    body_a = client.get("/api/v1/analytics/requests", headers=_h(ta)).json()
    assert body_a["total"] == 1
    body_b = client.get("/api/v1/analytics/requests", headers=_h(tb)).json()
    assert body_b["total"] == 2


def test_requires_auth(client):
    assert client.get("/api/v1/analytics/requests").status_code == 401
