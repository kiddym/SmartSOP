import pytest
from sqlalchemy import select

from app.services import auth_service
from app.schemas.auth import RegisterRequest, LoginRequest
from app.models.company import Company
from app.models.role import Role


def _register(db, company="Acme", email="a@acme.com"):
    return auth_service.register(db, RegisterRequest(
        company_name=company, email=email, password="secret123", name="Alice"))


def test_register_creates_company_and_4_roles(db):
    user = _register(db)
    company = db.get(Company, user.company_id)
    assert company is not None
    from app import tenant
    token = tenant.set_current_company_id(company.id)
    try:
        roles = db.execute(select(Role)).scalars().all()
    finally:
        tenant.reset_current_company_id(token)
    assert {r.code for r in roles} == {"super_admin", "admin", "technician", "viewer"}
    sa = next(r for r in roles if r.code == "super_admin")
    assert user.role_id == sa.id


def test_register_duplicate_slug_raises(db):
    _register(db, company="Acme")
    with pytest.raises(auth_service.AuthError):
        _register(db, company="Acme", email="b@acme.com")


def test_login_success(db):
    _register(db)
    user = auth_service.authenticate(db, LoginRequest(email="a@acme.com", password="secret123"))
    assert user.email == "a@acme.com"


def test_login_wrong_password(db):
    _register(db)
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate(db, LoginRequest(email="a@acme.com", password="nope"))


def test_login_ambiguous_email_requires_slug(db):
    auth_service.register(db, RegisterRequest(company_name="Acme",
        email="same@x.com", password="secret123", name="A"))
    auth_service.register(db, RegisterRequest(company_name="Globex",
        email="same@x.com", password="secret123", name="B"))
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate(db, LoginRequest(email="same@x.com", password="secret123"))
    u = auth_service.authenticate(db, LoginRequest(email="same@x.com",
        password="secret123", company_slug="globex"))
    assert u.company_id is not None
