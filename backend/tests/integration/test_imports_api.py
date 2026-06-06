"""实体级 CSV 批量导入（/api/v1/imports/{entity}）。

模板下载返回表头；上传合法 CSV 创建实体（assets/locations/parts）；
含一行非法（缺必填/关联名不存在）→该行计 failed 且其余成功；
无 create 权限 403；租户隔离（A 租户的分类名在 B 租户解析不到）。

注意：本功能是独立的实体 CSV 导入，与 batch_imports（SOP Word 批量解析）无关。
"""

from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.usefixtures("_enterprise_default")


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company: str = "Acme", email: str = "admin@acme.com") -> str:
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _upload(client, token: str, entity: str, content: str):
    return client.post(
        f"/api/v1/imports/{entity}",
        headers=_h(token),
        files={"file": (f"{entity}.csv", io.BytesIO(content.encode("utf-8")), "text/csv")},
    )


_EXPECTED = {
    "assets": ["name", "status", "category", "location", "manufacturer", "model", "serial_number"],
    "locations": ["name", "address", "parent"],
    "parts": ["name", "description", "unit", "cost", "quantity", "min_quantity", "category"],
    "meters": ["name", "unit", "asset", "location", "category"],
}


@pytest.mark.parametrize("entity", list(_EXPECTED))
def test_template_returns_header(client, entity: str) -> None:
    t = _admin(client)
    r = client.get(f"/api/v1/imports/{entity}/template", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert r.text.startswith("﻿")  # BOM
    lines = [ln for ln in r.text.replace("﻿", "").splitlines() if ln.strip()]
    assert lines[0].split(",") == _EXPECTED[entity]
    # 表头 + 示例行
    assert len(lines) >= 2


def test_template_unsupported_entity_400(client) -> None:
    t = _admin(client)
    r = client.get("/api/v1/imports/widgets/template", headers=_h(t))
    assert r.status_code == 400


def test_import_assets_creates_rows(client) -> None:
    t = _admin(client)
    csv_text = (
        "name,status,category,location,manufacturer,model,serial_number\n"
        "泵A,OPERATIONAL,,,ACME,X1,SN-1\n"
        "泵B,STANDBY,,,ACME,X2,SN-2\n"
    )
    r = _upload(client, t, "assets", csv_text)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"created": 2, "failed": 0, "errors": []}
    listed = client.get("/api/v1/assets", headers=_h(t)).json()
    assert {a["name"] for a in listed} >= {"泵A", "泵B"}


def test_import_locations_creates_rows(client) -> None:
    t = _admin(client)
    csv_text = "name,address,parent\n厂区甲,路1号,\n厂区乙,路2号,\n"
    r = _upload(client, t, "locations", csv_text)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2


def test_import_parts_creates_rows(client) -> None:
    t = _admin(client)
    csv_text = (
        "name,description,unit,cost,quantity,min_quantity,category\n"
        "滤芯,高效,个,12.5,10,2,\n"
    )
    r = _upload(client, t, "parts", csv_text)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1
    parts = client.get("/api/v1/parts", headers=_h(t)).json()
    p = next(x for x in parts if x["name"] == "滤芯")
    from decimal import Decimal

    assert Decimal(str(p["quantity"])) == Decimal("10")
    assert Decimal(str(p["cost"])) == Decimal("12.5")


def test_import_resolves_related_category_by_name(client) -> None:
    t = _admin(client)
    cat = client.post(
        "/api/v1/asset-categories", headers=_h(t), json={"name": "泵类"}
    )
    assert cat.status_code in (200, 201), cat.text
    csv_text = (
        "name,status,category,location,manufacturer,model,serial_number\n"
        "泵C,OPERATIONAL,泵类,,ACME,X3,SN-3\n"
    )
    r = _upload(client, t, "assets", csv_text)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1
    a = next(x for x in client.get("/api/v1/assets", headers=_h(t)).json() if x["name"] == "泵C")
    assert a["category_id"] == cat.json()["id"]


def test_import_partial_failure_isolates_bad_row(client) -> None:
    t = _admin(client)
    # 行2 合法；行3 缺 name；行4 关联分类名不存在 → 2 失败 1 成功，互不污染。
    csv_text = (
        "name,status,category,location,manufacturer,model,serial_number\n"
        "好泵,OPERATIONAL,,,ACME,X1,SN-1\n"
        ",OPERATIONAL,,,ACME,X2,SN-2\n"
        "缺分类泵,OPERATIONAL,不存在的分类,,ACME,X3,SN-3\n"
    )
    r = _upload(client, t, "assets", csv_text)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1
    assert body["failed"] == 2
    rows = {e["row"] for e in body["errors"]}
    assert rows == {3, 4}
    # 成功行确实落库，失败行不落库。
    names = {a["name"] for a in client.get("/api/v1/assets", headers=_h(t)).json()}
    assert "好泵" in names
    assert "缺分类泵" not in names


def test_import_requires_create_permission(client) -> None:
    admin = _admin(client)
    # 造一个只读角色用户（view 但无 create）。
    role = client.post(
        "/api/v1/roles",
        headers=_h(admin),
        json={"name": "只读", "code": "ro_custom", "permissions": ["asset.view"]},
    )
    assert role.status_code in (200, 201), role.text
    invited = client.post(
        "/api/v1/users",
        headers=_h(admin),
        json={
            "email": "ro@acme.com",
            "name": "RO",
            "password": "secret123",
            "role_id": role.json()["id"],
        },
    )
    assert invited.status_code in (200, 201), invited.text
    ro_token = client.post(
        "/api/v1/auth/login",
        json={"email": "ro@acme.com", "password": "secret123"},
    ).json()["access_token"]
    csv_text = (
        "name,status,category,location,manufacturer,model,serial_number\n"
        "泵X,OPERATIONAL,,,ACME,X1,SN-1\n"
    )
    r = _upload(client, ro_token, "assets", csv_text)
    assert r.status_code == 403, r.text


def test_import_tenant_isolation_on_related_names(client) -> None:
    # A 租户建分类“专属”；B 租户导入引用该名 → 解析不到（租户隔离）→ 该行失败。
    ta = _admin(client, company="Acme", email="a@acme.com")
    client.post("/api/v1/asset-categories", headers=_h(ta), json={"name": "专属"})
    tb = _admin(client, company="Beta", email="b@beta.com")
    csv_text = (
        "name,status,category,location,manufacturer,model,serial_number\n"
        "泵Z,OPERATIONAL,专属,,ACME,X1,SN-1\n"
    )
    r = _upload(client, tb, "assets", csv_text)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 0
    assert body["failed"] == 1
    assert "专属" in body["errors"][0]["message"]
