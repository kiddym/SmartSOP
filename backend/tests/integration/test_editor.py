"""程序元数据 PUT（meta-only）集成测试（B4a）。结构改动走 /nodes 颗粒度端点。"""

from fastapi.testclient import TestClient

from tests.conftest import Factory


def test_put_procedure_updates_meta_only(client: TestClient, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, status="DRAFT", is_current=True)
    resp = client.put(
        f"/api/v1/procedures/{proc.id}",
        headers={"If-Match": str(proc.revision)},
        json={"name": "新名", "level_of_use": "reference", "signoff_enabled": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "新名"
    assert body["signoff_enabled"] is True
    assert body["revision"] == proc.revision + 1
    assert "id_map" not in body


def test_put_procedure_rejects_non_draft(client: TestClient, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, status="PUBLISHED", is_current=True)
    resp = client.put(
        f"/api/v1/procedures/{proc.id}",
        headers={"If-Match": str(proc.revision)},
        json={"name": "x", "level_of_use": "reference"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PROCEDURE_READONLY"
