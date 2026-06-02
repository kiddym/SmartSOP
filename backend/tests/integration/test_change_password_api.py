def _register_and_token(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Acme",
            "email": "a@acme.com",
            "password": "secret123",
            "name": "Alice",
        },
    )
    return r.json()["access_token"]


def test_change_password_success(client):
    tok = _register_and_token(client)
    r = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {tok}"},
        json={"old_password": "secret123", "new_password": "newsecret456"},
    )
    assert r.status_code == 200, r.text
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "a@acme.com", "password": "newsecret456"}
        ).status_code
        == 200
    )


def test_change_password_wrong_old_400(client):
    tok = _register_and_token(client)
    r = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {tok}"},
        json={"old_password": "WRONG", "new_password": "newsecret456"},
    )
    assert r.status_code == 400


def test_change_password_requires_auth(client):
    assert (
        client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "x", "new_password": "newsecret456"},
        ).status_code
        == 401
    )
