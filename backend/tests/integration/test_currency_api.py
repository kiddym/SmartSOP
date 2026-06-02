def _admin_token(client):
    return client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Acme",
            "email": "a@acme.com",
            "password": "secret123",
            "name": "A",
        },
    ).json()["access_token"]


def test_currency_crud_super_admin(client):
    tok = _admin_token(client)  # 首用户=super_admin
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        "/api/v1/currencies", headers=h, json={"code": "CNY", "name": "人民币", "symbol": "¥"}
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert client.get("/api/v1/currencies", headers=h).status_code == 200
    assert any(c["code"] == "CNY" for c in client.get("/api/v1/currencies", headers=h).json())
    assert client.delete(f"/api/v1/currencies/{cid}", headers=h).status_code == 204


def test_currency_duplicate_code_409(client):
    tok = _admin_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    client.post("/api/v1/currencies", headers=h, json={"code": "USD", "name": "美元"})
    r = client.post("/api/v1/currencies", headers=h, json={"code": "USD", "name": "美元2"})
    assert r.status_code == 409


def test_currency_create_forbidden_for_unprivileged(client, db):
    from sqlalchemy import select

    from app import tenant
    from app.models.user import User
    from app.services import invitation_service

    client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Acme",
            "email": "admin@acme.com",
            "password": "secret123",
            "name": "Admin",
        },
    )
    with tenant.bypass_tenant_scope():
        admin = db.execute(select(User).where(User.email == "admin@acme.com")).scalar_one()
    _inv, raw = invitation_service.invite(
        db, company_id=admin.company_id, email="member@acme.com", role_id=None, invited_by=admin.id
    )
    db.commit()
    acc = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw, "name": "Member", "password": "memberpw1"},
    ).json()
    h = {"Authorization": f"Bearer {acc['access_token']}"}
    r = client.post("/api/v1/currencies", headers=h, json={"code": "EUR", "name": "欧元"})
    assert r.status_code == 403, r
