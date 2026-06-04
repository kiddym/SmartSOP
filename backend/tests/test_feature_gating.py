"""feature gate 与 RBAC 正交叠加：free 锁高级模块，pro 解锁，super_admin 不绕。"""

from sqlalchemy import select

from app.models.company import Company


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _set_plan(db, *, plan, status="active"):
    company = db.execute(select(Company)).scalars().first()
    company.plan = plan
    company.subscription_status = status
    db.commit()


def test_meters_locked_on_free_returns_402(client):
    t = _admin(client)  # 新公司默认 free
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["code"] == "FEATURE_LOCKED"


def test_meters_unlocked_on_pro(client, db):
    t = _admin(client)
    _set_plan(db, plan="pro")
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 200, r.text


def test_super_admin_does_not_bypass_feature_gate(client, db):
    # 注册用户即 super_admin（通配权限），但 free 档仍被 feature gate 拦
    t = _admin(client)
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text


def test_pro_but_inactive_status_downgrades(client, db):
    t = _admin(client)
    _set_plan(db, plan="pro", status="past_due")
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text
