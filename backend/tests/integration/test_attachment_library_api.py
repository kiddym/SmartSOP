"""全局文件库端点集成测试（GET /attachments/library + hidden/file_type）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

ATT = "/api/v1/attachments"
LIB = "/api/v1/attachments/library"


def _register(client: TestClient, company: str, email: str) -> str:
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _make_asset(db: Session, token: str, custom_id: str = "A1") -> str:
    from app import security, tenant
    from app.models.maintenance_asset import Asset

    company_id = security.decode_token(token)["company_id"]
    tenant.set_current_company_id(company_id)
    db.add(Asset(custom_id=custom_id, name="泵"))
    db.commit()
    aid = db.query(Asset).filter(Asset.custom_id == custom_id).one().id
    tenant.set_current_company_id(None)
    return aid


def _make_request(client: TestClient, token: str, title: str = "漏水报修") -> str:
    h = {"Authorization": f"Bearer {token}"}
    return client.post("/api/v1/requests", headers=h, json={"title": title}).json()["id"]


def _upload(
    client: TestClient,
    h: dict[str, str],
    entity_type: str,
    entity_id: str,
    name: str,
    content_type: str,
) -> dict:
    up = client.post(
        ATT,
        headers=h,
        data={"entity_type": entity_type, "entity_id": entity_id},
        files={"file": (name, b"DATA", content_type)},
    )
    assert up.status_code == 201, up.text
    return up.json()


def test_library_lists_across_entities_and_infers_file_type(
    client: TestClient, db: Session, storage_tmp: Path
) -> None:
    tok = _register(client, "Acme", "a@acme.com")
    h = {"Authorization": f"Bearer {tok}"}
    aid = _make_asset(db, tok)
    rid = _make_request(client, tok)

    img = _upload(client, h, "asset", aid, "photo.png", "image/png")
    doc = _upload(client, h, "request", rid, "manual.pdf", "application/pdf")

    # 上传即返回 file_type/hidden。
    assert img["file_type"] == "IMAGE"
    assert doc["file_type"] == "OTHER"
    assert img["hidden"] is False

    page = client.get(LIB, headers=h)
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] == 2
    ids = {it["id"] for it in body["items"]}
    assert ids == {img["id"], doc["id"]}
    # 跨实体字段都在。
    by_id = {it["id"]: it for it in body["items"]}
    assert by_id[img["id"]]["entity_type"] == "asset"
    assert by_id[img["id"]]["entity_id"] == aid
    assert by_id[doc["id"]]["entity_type"] == "request"


def test_library_filters_file_type_and_q(
    client: TestClient, db: Session, storage_tmp: Path
) -> None:
    tok = _register(client, "Acme", "a@acme.com")
    h = {"Authorization": f"Bearer {tok}"}
    aid = _make_asset(db, tok)

    img = _upload(client, h, "asset", aid, "diagram.png", "image/png")
    _upload(client, h, "asset", aid, "spec.pdf", "application/pdf")

    only_img = client.get(LIB, headers=h, params={"file_type": "IMAGE"}).json()
    assert only_img["total"] == 1
    assert only_img["items"][0]["id"] == img["id"]

    by_q = client.get(LIB, headers=h, params={"q": "spec"}).json()
    assert by_q["total"] == 1
    assert by_q["items"][0]["file_name"] == "spec.pdf"

    by_entity = client.get(LIB, headers=h, params={"entity_type": "request"}).json()
    assert by_entity["total"] == 0


def test_library_hidden_filter_and_toggle(
    client: TestClient, db: Session, storage_tmp: Path
) -> None:
    tok = _register(client, "Acme", "a@acme.com")
    h = {"Authorization": f"Bearer {tok}"}
    aid = _make_asset(db, tok)
    att = _upload(client, h, "asset", aid, "secret.pdf", "application/pdf")

    # 默认 library 含此附件。
    assert client.get(LIB, headers=h).json()["total"] == 1

    # 改 hidden=true。
    upd = client.put(f"{ATT}/{att['id']}", headers=h, json={"hidden": True})
    assert upd.status_code == 200 and upd.json()["hidden"] is True

    # 默认（不含 hidden）→ 不出现。
    assert client.get(LIB, headers=h).json()["total"] == 0
    # include_hidden=true → 出现。
    incl = client.get(LIB, headers=h, params={"include_hidden": True}).json()
    assert incl["total"] == 1
    assert incl["items"][0]["hidden"] is True

    # 改回可见 → library 反映。
    client.put(f"{ATT}/{att['id']}", headers=h, json={"hidden": False})
    assert client.get(LIB, headers=h).json()["total"] == 1


def test_library_cross_tenant_isolation(client: TestClient, db: Session, storage_tmp: Path) -> None:
    tokA = _register(client, "CoA", "a@a.com")
    tokB = _register(client, "CoB", "b@b.com")
    hA = {"Authorization": f"Bearer {tokA}"}
    hB = {"Authorization": f"Bearer {tokB}"}
    aid = _make_asset(db, tokA)
    _upload(client, hA, "asset", aid, "private.pdf", "application/pdf")

    # A 看得到自己的。
    assert client.get(LIB, headers=hA).json()["total"] == 1
    # B 看不到 A 的（租户隔离）。
    assert client.get(LIB, headers=hB).json()["total"] == 0


def test_library_requires_auth(client: TestClient, storage_tmp: Path) -> None:
    assert client.get(LIB).status_code == 401
