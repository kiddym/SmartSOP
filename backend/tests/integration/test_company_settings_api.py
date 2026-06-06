def _token(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "A"},
    ).json()["access_token"]


def test_get_returns_defaults_then_update(client):
    h = {"Authorization": f"Bearer {_token(client)}"}
    r = client.get("/api/v1/company-settings", headers=h)
    assert r.status_code == 200
    assert r.json()["date_format"] == "YYYY-MM-DD"
    u = client.put(
        "/api/v1/company-settings", headers=h, json={"timezone": "UTC", "auto_assign": True}
    )
    assert u.status_code == 200, u.text
    assert u.json()["timezone"] == "UTC"
    assert u.json()["auto_assign"] is True
    # 持久化
    assert client.get("/api/v1/company-settings", headers=h).json()["timezone"] == "UTC"


def test_general_preferences_defaults_and_update(client):
    """通用偏好开关默认值合理且可更新持久化。"""
    h = {"Authorization": f"Bearer {_token(client)}"}
    r = client.get("/api/v1/company-settings", headers=h).json()
    # 默认：工时计入总成本=True，其余开关 False，PM 提前提醒天数=0
    assert r["labor_cost_in_total_cost"] is True
    assert r["ask_feedback_on_wo_closed"] is False
    assert r["auto_assign_requests"] is False
    assert r["days_before_pm_notification"] == 0
    assert r["language"] == "zh-CN"
    u = client.put(
        "/api/v1/company-settings",
        headers=h,
        json={
            "business_type": "Manufacturing",
            "ask_feedback_on_wo_closed": True,
            "labor_cost_in_total_cost": False,
            "days_before_pm_notification": 7,
            "auto_assign_requests": True,
        },
    )
    assert u.status_code == 200, u.text
    body = u.json()
    assert body["business_type"] == "Manufacturing"
    assert body["ask_feedback_on_wo_closed"] is True
    assert body["labor_cost_in_total_cost"] is False
    assert body["days_before_pm_notification"] == 7
    # 持久化
    again = client.get("/api/v1/company-settings", headers=h).json()
    assert again["auto_assign_requests"] is True


def test_settings_isolated_per_company(client):
    """两公司各自独立的 settings。"""
    hA = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/register', json={'company_name': 'CoA', 'email': 'a@a.com', 'password': 'secret123', 'name': 'A'}).json()['access_token']}"
    }
    hB = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/register', json={'company_name': 'CoB', 'email': 'b@b.com', 'password': 'secret123', 'name': 'B'}).json()['access_token']}"
    }
    client.put("/api/v1/company-settings", headers=hA, json={"timezone": "UTC"})
    # B 仍是默认
    assert client.get("/api/v1/company-settings", headers=hB).json()["timezone"] == "Asia/Shanghai"
    assert client.get("/api/v1/company-settings", headers=hA).json()["timezone"] == "UTC"


def test_update_forbidden_for_unprivileged(client, db):
    """无 company.settings 权限的普通成员不能改公司配置（PUT 403）；但仍可读（GET 200）。"""
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
    tok = client.post(
        "/api/v1/auth/accept-invite", json={"token": raw, "name": "Member", "password": "memberpw1"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/company-settings", headers=h).status_code == 200
    assert (
        client.put("/api/v1/company-settings", headers=h, json={"timezone": "UTC"}).status_code
        == 403
    )
