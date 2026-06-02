"""Security utilities: password hashing and JWT tokens."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import bcrypt as _bcrypt
from jose import JWTError, jwt

from app.config import settings


class TokenError(Exception):
    """Raised when a JWT cannot be decoded or is invalid."""


def _prehash(password: str) -> bytes:
    """SHA-256 then base64 so the bcrypt input is always 44 bytes.

    bcrypt silently caps the password at 72 bytes (and recent bcrypt raises on
    longer input). Our schemas allow up to 128 chars, and multibyte (e.g.
    Chinese) passwords reach 72 bytes well under that. Pre-hashing with SHA-256
    keeps the full password entropy while staying within bcrypt's limit — the
    standard bcrypt_sha256 construction.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    """Return a bcrypt(sha256(password)) hash."""
    return _bcrypt.hashpw(_prehash(password), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True iff *plain* matches the bcrypt(sha256(...)) *hashed* value."""
    return _bcrypt.checkpw(_prehash(plain), hashed.encode("utf-8"))


def generate_token() -> str:
    """生成 URL-safe 随机 token（明文仅入邮件，DB 存其哈希）。"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """token 的 sha256 十六进制（DB 存哈希，不存明文）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_token(
    *,
    user_id: str,
    company_id: str,
    role_code: str | None,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "role_code": role_code,
        "type": token_type,
        "exp": datetime.now(UTC) + expires_delta,
    }
    return cast(str, jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm))


def create_access_token(*, user_id: str, company_id: str, role_code: str | None) -> str:
    return _create_token(
        user_id=user_id,
        company_id=company_id,
        role_code=role_code,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(*, user_id: str, company_id: str, role_code: str | None) -> str:
    return _create_token(
        user_id=user_id,
        company_id=company_id,
        role_code=role_code,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return cast(
            dict[str, Any],
            jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm]),
        )
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
