"""表单字段配置 API（C1 基础设施，服务请求/工单表单字段显隐必填）。"""


def _token(client, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_get_seeds_request_form_defaults(client):
    h = _h(_token(client))
    r = client.get("/api/v1/field-configurations/REQUEST", headers=h)
    assert r.status_code == 200, r.text
    rows = r.json()
    names = {row["field_name"] for row in rows}
    # 请求表单可配置字段都应被种子化
    assert {"asset", "location", "priority", "due_date", "description"} <= names
    # 默认全部可见
    assert all(row["visible"] for row in rows)


def test_get_seeds_work_order_form_defaults(client):
    h = _h(_token(client))
    rows = client.get("/api/v1/field-configurations/WORK_ORDER", headers=h).json()
    names = {row["field_name"] for row in rows}
    assert {"asset", "location", "assignee", "category", "priority"} <= names


def test_unknown_form_key_404(client):
    h = _h(_token(client))
    assert client.get("/api/v1/field-configurations/BOGUS", headers=h).status_code == 404


def test_put_updates_visibility_and_required(client):
    h = _h(_token(client))
    client.get("/api/v1/field-configurations/REQUEST", headers=h)  # seed
    r = client.put(
        "/api/v1/field-configurations/REQUEST",
        headers=h,
        json=[
            {"field_name": "asset", "visible": True, "required": True},
            {"field_name": "location", "visible": False, "required": False},
        ],
    )
    assert r.status_code == 200, r.text
    by_name = {row["field_name"]: row for row in r.json()}
    assert by_name["asset"]["required"] is True
    assert by_name["location"]["visible"] is False
    # 持久化
    again = {row["field_name"]: row for row in client.get(
        "/api/v1/field-configurations/REQUEST", headers=h
    ).json()}
    assert again["asset"]["required"] is True
    assert again["location"]["visible"] is False


def test_put_rejects_unknown_field(client):
    h = _h(_token(client))
    r = client.put(
        "/api/v1/field-configurations/REQUEST",
        headers=h,
        json=[{"field_name": "nonsense_field", "visible": True, "required": False}],
    )
    assert r.status_code == 422


def test_put_requires_company_settings_permission(client, db):
    """无 company.settings 权限的成员只能读不能改。"""
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
        db, company_id=admin.company_id, email="m@acme.com", role_id=None, invited_by=admin.id
    )
    db.commit()
    tok = client.post(
        "/api/v1/auth/accept-invite", json={"token": raw, "name": "M", "password": "memberpw1"}
    ).json()["access_token"]
    h = _h(tok)
    assert client.get("/api/v1/field-configurations/REQUEST", headers=h).status_code == 200
    assert (
        client.put(
            "/api/v1/field-configurations/REQUEST",
            headers=h,
            json=[{"field_name": "asset", "visible": True, "required": True}],
        ).status_code
        == 403
    )


def test_config_isolated_per_company(client):
    hA = _h(_token(client, "CoA", "a@a.com"))
    hB = _h(_token(client, "CoB", "b@b.com"))
    client.get("/api/v1/field-configurations/REQUEST", headers=hA)
    client.put(
        "/api/v1/field-configurations/REQUEST",
        headers=hA,
        json=[{"field_name": "asset", "visible": False, "required": False}],
    )
    b_rows = {r["field_name"]: r for r in client.get(
        "/api/v1/field-configurations/REQUEST", headers=hB
    ).json()}
    assert b_rows["asset"]["visible"] is True  # B 不受 A 影响
