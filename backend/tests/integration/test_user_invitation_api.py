from sqlalchemy import select

from app import tenant
from app.models.user import User


def _register(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "Admin"}).json()


def _admin_token(client, company="Acme", email="admin@acme.com"):
    return _register(client, company, email)["access_token"]


def test_invite_then_accept(client, db):
    from app.services import invitation_service
    _admin_token(client)
    with tenant.bypass_tenant_scope():
        admin = db.execute(select(User).where(User.email == "admin@acme.com")).scalar_one()
    _inv, raw = invitation_service.invite(
        db, company_id=admin.company_id, email="bob@acme.com", role_id=None, invited_by=admin.id)
    db.commit()
    acc = client.post("/api/v1/auth/accept-invite",
                      json={"token": raw, "name": "Bob", "password": "bobsecret1"})
    assert acc.status_code == 200, acc.text
    assert acc.json()["access_token"]
    login = client.post("/api/v1/auth/login", json={"email": "bob@acme.com", "password": "bobsecret1"})
    assert login.status_code == 200
    # bob created in the right company with no role
    with tenant.bypass_tenant_scope():
        bob = db.execute(select(User).where(User.email == "bob@acme.com")).scalar_one()
    assert bob.company_id == admin.company_id


def test_invite_via_endpoint_returns_201(client):
    tok = _admin_token(client)
    r = client.post("/api/v1/users/invite", headers={"Authorization": f"Bearer {tok}"},
                    json={"email": "carol@acme.com"})
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "carol@acme.com"
    assert r.json()["status"] == "pending"


def test_invite_existing_email_409(client):
    tok = _admin_token(client)
    r = client.post("/api/v1/users/invite", headers={"Authorization": f"Bearer {tok}"},
                    json={"email": "admin@acme.com"})  # already a member
    assert r.status_code == 409


def test_invite_requires_auth(client):
    assert client.post("/api/v1/users/invite", json={"email": "x@acme.com"}).status_code == 401


def test_accept_invalid_token_400(client):
    r = client.post("/api/v1/auth/accept-invite",
                    json={"token": "bogus", "name": "X", "password": "password1"})
    assert r.status_code == 400


def test_cross_tenant_invitation_isolation(client, db):
    """A 公司的邀请不应泄漏到 B；B 用同一邮箱注册不受 A 邀请影响。"""
    from app.services import invitation_service
    # company A
    _register(client, company="AcmeA", email="adminA@a.com")
    with tenant.bypass_tenant_scope():
        adminA = db.execute(select(User).where(User.email == "adminA@a.com")).scalar_one()
    _invA, rawA = invitation_service.invite(
        db, company_id=adminA.company_id, email="shared@x.com", role_id=None, invited_by=adminA.id)
    db.commit()
    # company B (separate registration)
    _register(client, company="AcmeB", email="adminB@b.com")
    with tenant.bypass_tenant_scope():
        adminB = db.execute(select(User).where(User.email == "adminB@b.com")).scalar_one()
    # accept A's invite → user created in A, not B
    acc = client.post("/api/v1/auth/accept-invite",
                      json={"token": rawA, "name": "Shared", "password": "sharedpw1"})
    assert acc.status_code == 200, acc.text
    with tenant.bypass_tenant_scope():
        shared = db.execute(select(User).where(User.email == "shared@x.com")).scalars().all()
    assert len(shared) == 1
    assert shared[0].company_id == adminA.company_id
    assert shared[0].company_id != adminB.company_id
