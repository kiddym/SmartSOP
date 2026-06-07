"""自定义字段定义 CRUD/归档/排序 API 集成测试。"""


def _admin(client, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _create(client, h, **over):
    body = {
        "entity_type": "work_order",
        "key": "severity",
        "name": "严重度",
        "field_type": "select",
        "options": [{"value": "high", "label": "高"}, {"value": "low", "label": "低"}],
    }
    body.update(over)
    return client.post("/api/v1/custom-fields", headers=h, json=body)


def test_create_and_list(client):
    h = _h(_admin(client))
    r = _create(client, h)
    assert r.status_code == 201, r.text
    rows = client.get("/api/v1/custom-fields?entity_type=work_order", headers=h).json()
    assert [x["key"] for x in rows] == ["severity"]


# key 不可改的机制是 CustomFieldUpdate schema 根本不含 key 字段（无法传入），故改名成功而 key 不变。
def test_key_immutable_via_no_field(client):
    h = _h(_admin(client))
    fid = _create(client, h).json()["id"]
    r = client.patch(
        f"/api/v1/custom-fields/{fid}",
        headers=h,
        json={"name": "Severity2", "options": [{"value": "high"}]},
    )
    assert r.status_code == 200
    assert (
        client.get("/api/v1/custom-fields?entity_type=work_order", headers=h).json()[0]["key"]
        == "severity"
    )


def test_bad_key_422(client):
    h = _h(_admin(client))
    assert _create(client, h, key="Bad Key", field_type="text", options=[]).status_code == 422


def test_dup_key_conflict(client):
    h = _h(_admin(client))
    _create(client, h, field_type="text", options=[])
    assert _create(client, h, field_type="text", options=[]).status_code == 409


def test_unknown_entity_type_rejected(client):
    h = _h(_admin(client))
    assert client.get("/api/v1/custom-fields?entity_type=bogus", headers=h).status_code == 400


def test_archive_excludes_from_active_list(client):
    h = _h(_admin(client))
    fid = _create(client, h, field_type="text", options=[]).json()["id"]
    client.patch(f"/api/v1/custom-fields/{fid}/archive", headers=h)
    assert client.get("/api/v1/custom-fields?entity_type=work_order", headers=h).json() == []
    assert (
        len(
            client.get(
                "/api/v1/custom-fields?entity_type=work_order&include_archived=true", headers=h
            ).json()
        )
        == 1
    )


def test_write_requires_company_settings(client, db):
    """无 company.settings 权限的成员只能读不能写。"""
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
    # 成员可以读（GET 200）
    assert client.get("/api/v1/custom-fields?entity_type=work_order", headers=h).status_code == 200
    # 成员不能写（POST 403）
    assert _create(client, h, field_type="text", options=[]).status_code == 403


def test_tenant_isolation(client):
    hA = _h(_admin(client, "CoA", "a@a.com"))
    hB = _h(_admin(client, "CoB", "b@b.com"))
    _create(client, hA, field_type="text", options=[])
    assert client.get("/api/v1/custom-fields?entity_type=work_order", headers=hB).json() == []


def test_reorder_changes_sort_order(client):
    h = _h(_admin(client))
    a = _create(client, h, key="a", field_type="text", options=[]).json()["id"]
    b = _create(client, h, key="b", field_type="text", options=[]).json()["id"]
    rows = client.post(
        "/api/v1/custom-fields/reorder?entity_type=work_order",
        headers=h,
        json={"ordered_ids": [b, a]},
    ).json()
    assert [r["key"] for r in rows] == ["b", "a"]
