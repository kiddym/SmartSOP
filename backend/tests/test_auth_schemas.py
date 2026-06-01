import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair


def test_register_valid():
    r = RegisterRequest(company_name="Acme", email="a@acme.com", password="secret123", name="Alice")
    assert r.email == "a@acme.com"


def test_register_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(company_name="Acme", email="a@acme.com", password="x", name="Alice")


def test_login_optional_slug():
    assert LoginRequest(email="a@acme.com", password="secret123").company_slug is None


def test_token_pair_default_type():
    assert TokenPair(access_token="a", refresh_token="r").token_type == "bearer"
