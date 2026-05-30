def _admin(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_get_company_me(client):
    t = _admin(client)
    r = client.get("/api/v1/companies/me", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Acme"
    assert r.json()["locale"] == "zh-CN"


def test_update_company(client):
    t = _admin(client)
    r = client.patch("/api/v1/companies/me", headers=_h(t), json={"name": "Acme Inc"})
    assert r.status_code == 200
    assert r.json()["name"] == "Acme Inc"


def test_company_me_requires_auth(client):
    assert client.get("/api/v1/companies/me").status_code == 401
