def _token(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "A"}).json()["access_token"]


def test_get_returns_defaults_then_update(client):
    h = {"Authorization": f"Bearer {_token(client)}"}
    r = client.get("/api/v1/company-settings", headers=h)
    assert r.status_code == 200
    assert r.json()["date_format"] == "YYYY-MM-DD"
    u = client.put("/api/v1/company-settings", headers=h, json={"timezone": "UTC", "auto_assign": True})
    assert u.status_code == 200, u.text
    assert u.json()["timezone"] == "UTC"
    assert u.json()["auto_assign"] is True
    # 持久化
    assert client.get("/api/v1/company-settings", headers=h).json()["timezone"] == "UTC"


def test_settings_isolated_per_company(client):
    """两公司各自独立的 settings。"""
    hA = {"Authorization": f"Bearer {client.post('/api/v1/auth/register', json={'company_name': 'CoA', 'email': 'a@a.com', 'password': 'secret123', 'name': 'A'}).json()['access_token']}"}
    hB = {"Authorization": f"Bearer {client.post('/api/v1/auth/register', json={'company_name': 'CoB', 'email': 'b@b.com', 'password': 'secret123', 'name': 'B'}).json()['access_token']}"}
    client.put("/api/v1/company-settings", headers=hA, json={"timezone": "UTC"})
    # B 仍是默认
    assert client.get("/api/v1/company-settings", headers=hB).json()["timezone"] == "Asia/Shanghai"
    assert client.get("/api/v1/company-settings", headers=hA).json()["timezone"] == "UTC"
