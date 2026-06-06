"""实体级 CSV 导出（/api/v1/exports/{entity}）。

逐类校验 200 + text/csv + 表头 + 至少一行数据；租户隔离；无 view 权限 403。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("_enterprise_default")


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company: str = "Acme", email: str = "admin@acme.com") -> str:
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _seed(client, t: str) -> None:
    """每类实体至少各建一行。"""
    client.post("/api/v1/work-orders", headers=_h(t), json={"title": "换油工单"})
    client.post("/api/v1/assets", headers=_h(t), json={"name": "泵A"})
    client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区甲"})
    client.post("/api/v1/parts", headers=_h(t), json={"name": "滤芯", "quantity": "5"})
    client.post("/api/v1/meters", headers=_h(t), json={"name": "温度表", "unit": "℃"})


_EXPECTED = {
    "work-orders": ["custom_id", "title", "status", "priority", "due_date", "asset", "category", "assignee"],
    "assets": ["custom_id", "name", "status", "category", "location", "manufacturer", "model", "serial_number"],
    "locations": ["custom_id", "name", "address", "parent"],
    "parts": ["custom_id", "name", "quantity", "min_quantity", "unit", "cost", "category"],
    "meters": ["custom_id", "name", "unit", "asset", "location", "category"],
}


@pytest.mark.parametrize("entity", list(_EXPECTED))
def test_export_returns_csv_with_header_and_row(client, entity: str) -> None:
    t = _admin(client)
    _seed(client, t)
    r = client.get(f"/api/v1/exports/{entity}", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    # BOM 前缀（Excel 识别 UTF-8）。
    assert r.text.startswith("﻿")
    lines = [ln for ln in r.text.replace("﻿", "").splitlines() if ln.strip()]
    assert lines[0].split(",") == _EXPECTED[entity]
    # 表头 + 至少一行数据。
    assert len(lines) >= 2


def test_export_resolves_related_names(client) -> None:
    t = _admin(client)
    loc = client.post("/api/v1/locations", headers=_h(t), json={"name": "锅炉房"}).json()
    client.post(
        "/api/v1/assets",
        headers=_h(t),
        json={"name": "锅炉1", "location_id": loc["id"], "manufacturer": "ACME"},
    )
    r = client.get("/api/v1/exports/assets", headers=_h(t))
    body = r.text
    # 关联位置解析成名称而非 id。
    assert "锅炉房" in body
    assert loc["id"] not in body
    assert "ACME" in body


def test_export_tenant_isolation(client) -> None:
    ta = _admin(client, company="Acme", email="admin@acme.com")
    tb = _admin(client, company="Beta", email="admin@beta.com")
    client.post("/api/v1/assets", headers=_h(ta), json={"name": "A公司资产"})
    client.post("/api/v1/assets", headers=_h(tb), json={"name": "B公司资产"})

    body_a = client.get("/api/v1/exports/assets", headers=_h(ta)).text
    assert "A公司资产" in body_a
    assert "B公司资产" not in body_a

    body_b = client.get("/api/v1/exports/assets", headers=_h(tb)).text
    assert "B公司资产" in body_b
    assert "A公司资产" not in body_b


def test_export_requires_authentication(client) -> None:
    assert client.get("/api/v1/exports/assets").status_code == 401


@pytest.mark.parametrize("entity", list(_EXPECTED))
def test_export_requires_view_permission(client, entity: str) -> None:
    admin = _admin(client)
    # requester 角色：仅 request.view/create，无任何实体 view 权限。
    roles = client.get("/api/v1/roles", headers=_h(admin)).json()
    requester_role = next(r for r in roles if r["code"] == "requester")["id"]
    client.post(
        "/api/v1/users",
        headers=_h(admin),
        json={
            "email": "req@acme.com",
            "password": "secret123",
            "name": "R",
            "role_id": requester_role,
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "req@acme.com", "password": "secret123", "company_slug": "acme"},
    ).json()["access_token"]
    assert client.get(f"/api/v1/exports/{entity}", headers=_h(token)).status_code == 403
