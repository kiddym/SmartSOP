"""platform 设档端点：仅 is_platform_admin 可改任意公司订阅。"""

from sqlalchemy import select

from app.models.company import Company
from app.models.user import User


def _admin(client, company, email):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug_part):
    return db.execute(select(Company).where(Company.name == slug_part)).scalar_one().id


def _make_platform_admin(db, email):
    u = db.execute(select(User).where(User.email == email)).scalar_one()
    u.is_platform_admin = True
    db.commit()


def test_non_platform_admin_forbidden(client, db):
    t = _admin(client, "Acme", "a@acme.com")
    cid = _company_id(db, "Acme")
    r = client.patch(
        f"/api/v1/platform/companies/{cid}/subscription",
        headers=_h(t),
        json={"plan": "pro", "subscription_status": "active"},
    )
    assert r.status_code == 403, r.text


def test_platform_admin_can_set_plan(client, db):
    t = _admin(client, "Acme", "a@acme.com")
    cid = _company_id(db, "Acme")
    _make_platform_admin(db, "a@acme.com")
    r = client.patch(
        f"/api/v1/platform/companies/{cid}/subscription",
        headers=_h(t),
        json={"plan": "pro", "subscription_status": "active"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"plan": "pro", "subscription_status": "active"}
    # 升档后该公司可访问高级模块
    assert client.get("/api/v1/meters", headers=_h(t)).status_code == 200


def test_unknown_company_404(client, db):
    t = _admin(client, "Acme", "a@acme.com")
    _make_platform_admin(db, "a@acme.com")
    r = client.patch(
        "/api/v1/platform/companies/nonexistent-id/subscription",
        headers=_h(t),
        json={"plan": "pro", "subscription_status": "active"},
    )
    assert r.status_code == 404, r.text


def test_invalid_plan_rejected(client, db):
    t = _admin(client, "Acme", "a@acme.com")
    cid = _company_id(db, "Acme")
    _make_platform_admin(db, "a@acme.com")
    r = client.patch(
        f"/api/v1/platform/companies/{cid}/subscription",
        headers=_h(t),
        json={"plan": "platinum", "subscription_status": "active"},
    )
    assert r.status_code == 422, r.text
