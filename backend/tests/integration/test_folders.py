"""文件夹端点集成测试（api-specification §5.1）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Factory

pytestmark = pytest.mark.usefixtures("_sop_auth")

BASE = "/api/v1/folders"


def test_create_and_get_folder(client: TestClient) -> None:
    resp = client.post(BASE, json={"name": "质检"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["prefix"] == ""
    assert body["full_path"] == "质检"
    assert body["system"] is False

    got = client.get(f"{BASE}/{body['id']}")
    assert got.status_code == 200
    assert got.json()["name"] == "质检"


def test_create_leaf_with_prefix(client: TestClient) -> None:
    resp = client.post(BASE, json={"name": "来料", "prefix": "QC"})
    assert resp.status_code == 201
    assert resp.json()["prefix"] == "QC"


def test_get_missing_folder_returns_404(client: TestClient) -> None:
    resp = client.get(f"{BASE}/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


def test_duplicate_name_returns_409(client: TestClient) -> None:
    client.post(BASE, json={"name": "dup"})
    resp = client.post(BASE, json={"name": "dup"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "FOLDER_NAME_DUPLICATE"


def test_list_pagination_shape(client: TestClient) -> None:
    # 每公司注册即自带 2 个系统文件夹（废止/归档），故总数 = 3 创建 + 2 系统 = 5。
    for i in range(3):
        client.post(BASE, json={"name": f"f{i}"})
    resp = client.get(BASE, params={"page": 1, "page_size": 2})
    body = resp.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total_pages"] == 3
    assert len(body["items"]) == 2


def test_tree_endpoint(client: TestClient) -> None:
    root = client.post(BASE, json={"name": "r"}).json()
    client.post(BASE, json={"name": "c", "parent_id": root["id"], "prefix": "CC"})
    resp = client.get(f"{BASE}/tree")
    assert resp.status_code == 200
    node = next(n for n in resp.json() if n["id"] == root["id"])
    assert len(node["children"]) == 1
    assert node["children"][0]["procedure_count"] == 0


def test_options_endpoint(client: TestClient) -> None:
    client.post(BASE, json={"name": "opt"})
    resp = client.get(f"{BASE}/options")
    assert resp.status_code == 200
    assert any(o["name"] == "opt" for o in resp.json())


def test_update_rename(client: TestClient) -> None:
    fid = client.post(BASE, json={"name": "old"}).json()["id"]
    resp = client.put(f"{BASE}/{fid}", json={"name": "new", "parent_id": None})
    assert resp.status_code == 200
    assert resp.json()["name"] == "new"


def test_delete_then_404(client: TestClient) -> None:
    fid = client.post(BASE, json={"name": "tmp"}).json()["id"]
    assert client.delete(f"{BASE}/{fid}").status_code == 204
    assert client.get(f"{BASE}/{fid}").status_code == 404


def test_delete_non_empty_returns_400(client: TestClient) -> None:
    parent = client.post(BASE, json={"name": "p"}).json()["id"]
    client.post(BASE, json={"name": "c", "parent_id": parent})
    resp = client.delete(f"{BASE}/{parent}")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "FOLDER_NOT_EMPTY"


def test_check_name_endpoint(client: TestClient) -> None:
    client.post(BASE, json={"name": "exists"})
    assert client.get(f"{BASE}/check-name", params={"name": "exists"}).json()["available"] is False
    assert client.get(f"{BASE}/check-name", params={"name": "free"}).json()["available"] is True


def test_check_prefix_endpoint(client: TestClient) -> None:
    client.post(BASE, json={"name": "leaf", "prefix": "PX"})
    assert client.get(f"{BASE}/check-prefix", params={"prefix": "PX"}).json()["available"] is False
    assert client.get(f"{BASE}/check-prefix", params={"prefix": "PY"}).json()["available"] is True


def test_batch_delete_atomic(client: TestClient) -> None:
    a = client.post(BASE, json={"name": "a"}).json()["id"]
    parent = client.post(BASE, json={"name": "p"}).json()["id"]
    client.post(BASE, json={"name": "c", "parent_id": parent})

    resp = client.post(f"{BASE}/batch-delete", json={"ids": [a, parent]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted_ids"] == []
    assert body["failed"][0]["code"] == "FOLDER_NOT_EMPTY"
    # 原子：a 未被删除
    assert client.get(f"{BASE}/{a}").status_code == 200


def test_depth_exceeded_returns_400(client: TestClient) -> None:
    parent: str | None = None
    for i in range(5):
        payload: dict[str, object] = {"name": f"L{i}"}
        if parent is not None:
            payload["parent_id"] = parent
        parent = client.post(BASE, json=payload).json()["id"]
    resp = client.post(BASE, json={"name": "L5", "parent_id": parent})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "FOLDER_DEPTH_EXCEEDED"


def test_system_folder_delete_protected(client: TestClient, factory: Factory) -> None:
    sys = factory.folder(name="废止", system=True, full_path="废止")
    resp = client.delete(f"{BASE}/{sys.id}")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "FOLDER_SYSTEM_PROTECTED"
