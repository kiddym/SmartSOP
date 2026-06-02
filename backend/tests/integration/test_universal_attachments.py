"""通用附件端点集成测试（多态 + RBAC + 跨租户）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

ATT = "/api/v1/attachments"


def _register(client: TestClient, company: str, email: str) -> str:
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _make_asset(client: TestClient, db: Session, token: str) -> str:
    from app import security, tenant
    from app.models.maintenance_asset import Asset

    company_id = security.decode_token(token)["company_id"]
    tenant.set_current_company_id(company_id)
    db.add(Asset(custom_id="A1", name="泵"))
    db.commit()
    aid = db.query(Asset).filter(Asset.company_id == company_id).one().id
    tenant.set_current_company_id(None)
    return aid


def test_generic_flow_on_asset(client: TestClient, db: Session, storage_tmp: Path) -> None:
    tok = _register(client, "Acme", "a@acme.com")
    h = {"Authorization": f"Bearer {tok}"}
    aid = _make_asset(client, db, tok)

    up = client.post(
        ATT, headers=h,
        data={"entity_type": "asset", "entity_id": aid, "description": "手册"},
        files={"file": ("手册.pdf", b"PDF", "application/pdf")},
    )
    assert up.status_code == 201, up.text
    att = up.json()
    assert att["entity_type"] == "asset" and att["entity_id"] == aid
    assert att["procedure_id"] is None  # 非 procedure，别名为 None

    listed = client.get(ATT, headers=h, params={"entity_type": "asset", "entity_id": aid})
    assert [a["id"] for a in listed.json()] == [att["id"]]

    dl = client.get(f"{ATT}/{att['id']}/download", headers=h)
    assert dl.status_code == 200 and dl.content == b"PDF"

    upd = client.put(f"{ATT}/{att['id']}", headers=h, json={"description": "改"})
    assert upd.status_code == 200 and upd.json()["description"] == "改"

    dele = client.delete(f"{ATT}/{att['id']}", headers=h)
    assert dele.status_code == 204
    assert client.get(ATT, headers=h, params={"entity_type": "asset", "entity_id": aid}).json() == []


def test_unknown_entity_type_400(client: TestClient, db: Session, storage_tmp: Path) -> None:
    h = {"Authorization": f"Bearer {_register(client, 'Acme', 'a@acme.com')}"}
    r = client.post(
        ATT, headers=h,
        data={"entity_type": "ghost", "entity_id": "x"},
        files={"file": ("a.txt", b"x", "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_ENTITY_TYPE"


def test_missing_host_404(client: TestClient, db: Session, storage_tmp: Path) -> None:
    h = {"Authorization": f"Bearer {_register(client, 'Acme', 'a@acme.com')}"}
    r = client.get(ATT, headers=h, params={"entity_type": "asset", "entity_id": "ghost"})
    assert r.status_code == 404


def test_cross_tenant_attachment_not_leaked(
    client: TestClient, db: Session, storage_tmp: Path
) -> None:
    tokA = _register(client, "CoA", "a@a.com")
    tokB = _register(client, "CoB", "b@b.com")
    hA = {"Authorization": f"Bearer {tokA}"}
    hB = {"Authorization": f"Bearer {tokB}"}
    aid = _make_asset(client, db, tokA)
    att = client.post(
        ATT, headers=hA,
        data={"entity_type": "asset", "entity_id": aid},
        files={"file": ("s.pdf", b"S", "application/pdf")},
    ).json()
    assert client.get(ATT, headers=hB, params={"entity_type": "asset", "entity_id": aid}).status_code == 404
    assert client.get(f"{ATT}/{att['id']}/download", headers=hB).status_code == 404
    assert client.put(f"{ATT}/{att['id']}", headers=hB, json={"description": "x"}).status_code == 404
    assert client.delete(f"{ATT}/{att['id']}", headers=hB).status_code == 404


def test_single_resource_endpoints_require_auth(client: TestClient, storage_tmp: Path) -> None:
    """通用单资源端点需认证：匿名访问 → 401。"""
    assert client.get(f"{ATT}/whatever/download").status_code == 401
    assert client.get(f"{ATT}/whatever/preview").status_code == 401
    assert client.put(f"{ATT}/whatever", json={"description": "x"}).status_code == 401
    assert client.delete(f"{ATT}/whatever").status_code == 401
    assert client.get(ATT, params={"entity_type": "asset", "entity_id": "x"}).status_code == 401
    assert client.post(ATT, data={"entity_type": "asset", "entity_id": "x"},
                       files={"file": ("a.txt", b"x", "text/plain")}).status_code == 401
