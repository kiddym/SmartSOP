from sqlalchemy import select

from app.models.email_outbox import EmailOutbox


def _register(client, email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": email, "password": "secret123", "name": "Alice"},
    )


def test_forgot_password_enqueues(client, db):
    _register(client)
    r = client.post("/api/v1/auth/forgot-password", json={"email": "a@acme.com"})
    assert r.status_code == 200
    from app import tenant

    with tenant.bypass_tenant_scope():
        mail = db.execute(
            select(EmailOutbox).where(EmailOutbox.type == "PASSWORD_RESET")
        ).scalar_one()
    assert mail.recipient_email == "a@acme.com"


def test_forgot_password_unknown_email_still_200(client):
    _register(client)
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@acme.com"})
    assert r.status_code == 200  # 防枚举


def test_reset_with_valid_token(client, db):
    _register(client)
    from app.services import password_reset_service

    raw = password_reset_service.request_reset(db, email="a@acme.com")  # 返回明文 token（仅测试用）
    db.commit()
    assert raw is not None
    r = client.post(
        "/api/v1/auth/reset-password", json={"token": raw, "new_password": "newsecret456"}
    )
    assert r.status_code == 200, r.text
    r2 = client.post(
        "/api/v1/auth/reset-password", json={"token": raw, "new_password": "again12345"}
    )
    assert r2.status_code in (400, 410)  # 旧 token 失效
    login = client.post(
        "/api/v1/auth/login", json={"email": "a@acme.com", "password": "newsecret456"}
    )
    assert login.status_code == 200
