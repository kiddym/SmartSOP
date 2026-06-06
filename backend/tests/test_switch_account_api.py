"""切换账户 API：普通用户无权、授权关系/平台管理员可切、安全口径（须有成员账户）。"""

from __future__ import annotations

from sqlalchemy import select

from app import tenant
from app.models.company import Company
from app.models.super_account_relation import SuperAccountRelation
from app.models.user import User


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, *, company, email):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _me_id(client, token):
    return client.get("/api/v1/auth/me", headers=_h(token)).json()["id"]


def _company(db, slug):
    with tenant.bypass_tenant_scope():
        return db.execute(select(Company).where(Company.slug == slug)).scalar_one()


def test_requires_auth(client):
    assert client.get("/api/v1/auth/switchable-accounts").status_code == 401
    assert client.post("/api/v1/auth/switch-account", json={"company_id": "x"}).status_code == 401


def test_normal_user_switchable_empty(client):
    t = _register(client, company="Acme", email="a@acme.com")
    r = client.get("/api/v1/auth/switchable-accounts", headers=_h(t))
    assert r.status_code == 200 and r.json() == []


def test_normal_user_switch_forbidden(client):
    t = _register(client, company="Acme", email="a@acme.com")
    other = _register(client, company="Beta", email="b@beta.com")
    other_company_id = client.get("/api/v1/auth/me", headers=_h(other)).json()["company_id"]
    r = client.post(
        "/api/v1/auth/switch-account",
        json={"company_id": other_company_id},
        headers=_h(t),
    )
    assert r.status_code == 403


def test_relation_without_member_account_forbidden(client, db):
    """有授权关系但目标公司无同 email 成员 → 403（不签发越权 token）。"""
    t = _register(client, company="Acme", email="shared@x.com")
    _register(client, company="Beta", email="other@x.com")
    me = _me_id(client, t)
    beta = _company(db, "beta")
    db.add(
        SuperAccountRelation(
            company_id=_company(db, "acme").id, super_user_id=me, target_company_id=beta.id
        )
    )
    db.commit()
    # switchable-accounts 不列出（无成员账户）
    assert client.get("/api/v1/auth/switchable-accounts", headers=_h(t)).json() == []
    # 直接切换也 403
    r = client.post(
        "/api/v1/auth/switch-account",
        json={"company_id": beta.id},
        headers=_h(t),
    )
    assert r.status_code == 403


def test_relation_with_member_account_switches(client, db):
    """有授权关系且目标公司有同 email 成员 → 列出 + 签发指向该成员的 token。"""
    t = _register(client, company="Acme", email="shared@x.com")
    t_beta = _register(client, company="Beta", email="beta-admin@x.com")
    me = _me_id(client, t)
    beta = _company(db, "beta")
    # 在 Beta 建一个同 email（shared@x.com）成员账户
    client.post(
        "/api/v1/users",
        headers=_h(t_beta),
        json={"email": "shared@x.com", "password": "secret123", "name": "SharedInBeta"},
    )
    db.add(
        SuperAccountRelation(
            company_id=_company(db, "acme").id, super_user_id=me, target_company_id=beta.id
        )
    )
    db.commit()

    listed = client.get("/api/v1/auth/switchable-accounts", headers=_h(t)).json()
    assert len(listed) == 1 and listed[0]["company_slug"] == "beta"

    r = client.post(
        "/api/v1/auth/switch-account",
        json={"company_id": beta.id},
        headers=_h(t),
    )
    assert r.status_code == 200
    new_token = r.json()["access_token"]
    me2 = client.get("/api/v1/auth/me", headers=_h(new_token)).json()
    # 切到的是 Beta 内的真实成员身份
    assert me2["company_id"] == beta.id
    assert me2["email"] == "shared@x.com"
    with tenant.bypass_tenant_scope():
        beta_member = db.execute(
            select(User).where(User.company_id == beta.id, User.email == "shared@x.com")
        ).scalar_one()
    assert me2["id"] == beta_member.id


def test_platform_admin_switches_any_company_with_member(client, db):
    """is_platform_admin 不限授权关系，但仍要求目标公司有同 email 成员账户。"""
    t = _register(client, company="Acme", email="ops@x.com")
    t_beta = _register(client, company="Beta", email="beta-admin@x.com")
    me = _me_id(client, t)
    beta = _company(db, "beta")
    # 标记为平台管理员
    with tenant.bypass_tenant_scope():
        u = db.get(User, me)
        u.is_platform_admin = True
        db.commit()
    # Beta 无同 email 成员 → 仍 403
    r0 = client.post("/api/v1/auth/switch-account", json={"company_id": beta.id}, headers=_h(t))
    assert r0.status_code == 403
    # 建 Beta 内同 email 成员后可切
    client.post(
        "/api/v1/users",
        headers=_h(t_beta),
        json={"email": "ops@x.com", "password": "secret123", "name": "OpsInBeta"},
    )
    r = client.post("/api/v1/auth/switch-account", json={"company_id": beta.id}, headers=_h(t))
    assert r.status_code == 200
    me2 = client.get("/api/v1/auth/me", headers=_h(r.json()["access_token"])).json()
    assert me2["company_id"] == beta.id and me2["email"] == "ops@x.com"
