import pytest

from app import security


def test_hash_and_verify():
    h = security.hash_password("secret123")
    assert h != "secret123"
    assert security.verify_password("secret123", h) is True
    assert security.verify_password("wrong", h) is False


def test_long_password_roundtrip():
    # >72 bytes (ASCII) and multibyte both work via SHA-256 prehash; no ValueError.
    long_ascii = "a" * 128
    h = security.hash_password(long_ascii)
    assert security.verify_password(long_ascii, h) is True
    assert security.verify_password("a" * 72, h) is False  # not truncated to 72

    chinese = "密码" * 40  # 80 chars, 240 bytes UTF-8
    hc = security.hash_password(chinese)
    assert security.verify_password(chinese, hc) is True


def test_access_token_roundtrip():
    token = security.create_access_token(user_id="u-5", company_id="c-9", role_code="admin")
    claims = security.decode_token(token)
    assert claims["sub"] == "u-5"
    assert claims["company_id"] == "c-9"
    assert claims["role_code"] == "admin"
    assert claims["type"] == "access"


def test_refresh_token_type():
    token = security.create_refresh_token(user_id="u-5", company_id="c-9", role_code="admin")
    assert security.decode_token(token)["type"] == "refresh"


def test_decode_invalid_raises():
    with pytest.raises(security.TokenError):
        security.decode_token("not-a-token")
