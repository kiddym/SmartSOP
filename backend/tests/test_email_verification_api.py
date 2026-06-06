"""邮箱验证 API：request 落 outbox、verify 置标记、过期/无效拒绝、不破注册即用。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app import security, tenant
from app.models.base import utcnow
from app.models.email_outbox import EmailOutbox
from app.models.user import User
from app.models.verification_token import VerificationToken
from app.services import email_verification_service


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, *, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _me(client, token):
    return client.get("/api/v1/auth/me", headers=_h(token)).json()


def test_register_user_unverified_by_default(client):
    t = _register(client)
    assert _me(client, t)["email_verified"] is False


def test_request_verification_enqueues_outbox(client, db):
    t = _register(client)
    r = client.post("/api/v1/auth/request-verification", headers=_h(t))
    assert r.status_code == 200
    with tenant.bypass_tenant_scope():
        rows = (
            db.execute(select(EmailOutbox).where(EmailOutbox.type == "EMAIL_VERIFICATION"))
            .scalars()
            .all()
        )
    assert len(rows) == 1 and rows[0].status == "pending"


def test_verify_email_valid_token_marks_verified(client, db):
    t = _register(client)
    me_id = _me(client, t)["id"]
    # 直接调 service 拿明文 token（路由丢弃明文）
    with tenant.bypass_tenant_scope():
        user = db.get(User, me_id)
        raw = email_verification_service.request_verification(db, user)
        db.commit()
    r = client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert r.status_code == 200
    assert _me(client, t)["email_verified"] is True


def test_verify_email_invalid_token_rejected(client):
    _register(client)
    r = client.post("/api/v1/auth/verify-email", json={"token": "bogus-token"})
    assert r.status_code == 400


def test_verify_email_expired_token_rejected(client, db):
    t = _register(client)
    me_id = _me(client, t)["id"]
    raw = security.generate_token()
    with tenant.bypass_tenant_scope():
        user = db.get(User, me_id)
        db.add(
            VerificationToken(
                user_id=user.id,
                company_id=user.company_id,
                token_hash=security.hash_token(raw),
                expires_at=utcnow() - timedelta(hours=1),
            )
        )
        db.commit()
    r = client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert r.status_code == 400
    assert _me(client, t)["email_verified"] is False


def test_verify_token_single_use(client, db):
    t = _register(client)
    me_id = _me(client, t)["id"]
    with tenant.bypass_tenant_scope():
        user = db.get(User, me_id)
        raw = email_verification_service.request_verification(db, user)
        db.commit()
    assert client.post("/api/v1/auth/verify-email", json={"token": raw}).status_code == 200
    # 二次使用应拒绝
    assert client.post("/api/v1/auth/verify-email", json={"token": raw}).status_code == 400


def test_request_verification_requires_auth(client):
    assert client.post("/api/v1/auth/request-verification").status_code == 401
