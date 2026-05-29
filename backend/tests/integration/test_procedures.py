"""程序端点集成测试（api-specification §5.2）。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.seed import run_seed
from tests.conftest import Factory

PROC = "/api/v1/procedures"
FOLDER = "/api/v1/folders"


def _make_leaf(client: TestClient, *, name: str = "叶子", prefix: str = "QC") -> str:
    return client.post(FOLDER, json={"name": name, "prefix": prefix}).json()["id"]


def _make_procedure(client: TestClient, folder_id: str, *, name: str = "启动 SOP") -> dict:
    resp = client.post(
        PROC, json={"folder_id": folder_id, "name": name, "level_of_use": "continuous"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_returns_code_and_draft(client: TestClient) -> None:
    leaf = _make_leaf(client)
    body = _make_procedure(client, leaf)
    assert body["code"] == "QC-00001"
    assert body["status"] == "DRAFT"
    assert body["version"] == 1
    assert body["is_current"] is True
    assert body["revision"] == 0


def test_create_invalid_level_of_use_returns_422(client: TestClient) -> None:
    leaf = _make_leaf(client)
    resp = client.post(PROC, json={"folder_id": leaf, "name": "x", "level_of_use": "bogus"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_FAILED"


def test_get_detail_shape(client: TestClient) -> None:
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf)["id"]
    resp = client.get(f"{PROC}/{pid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["procedure"]["id"] == pid
    assert "fields" in body


def test_list_pagination(client: TestClient) -> None:
    leaf = _make_leaf(client)
    for i in range(3):
        _make_procedure(client, leaf, name=f"p{i}")
    resp = client.get(PROC, params={"page": 1, "page_size": 2})
    body = resp.json()
    assert body["total"] == 3
    assert body["total_pages"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["version_count_in_group"] == 1


def test_update_without_if_match_returns_412(client: TestClient) -> None:
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf)["id"]
    resp = client.put(f"{PROC}/{pid}", json={"name": "改名", "level_of_use": "reference"})
    assert resp.status_code == 412
    assert resp.json()["detail"]["code"] == "IF_MATCH_REQUIRED"


def test_update_wrong_if_match_returns_409(client: TestClient) -> None:
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf)["id"]
    resp = client.put(
        f"{PROC}/{pid}",
        json={"name": "改名", "level_of_use": "reference"},
        headers={"If-Match": "99"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "VERSION_CONFLICT"


def test_update_correct_if_match_succeeds(client: TestClient) -> None:
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf)["id"]
    resp = client.put(
        f"{PROC}/{pid}",
        json={"name": "新名", "level_of_use": "reference"},
        headers={"If-Match": "0"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "新名"
    assert body["revision"] == 1


def test_transition_publish(client: TestClient) -> None:
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf)["id"]
    resp = client.post(
        f"{PROC}/{pid}/transition", json={"status": "PUBLISHED"}, headers={"If-Match": "0"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PUBLISHED"


def test_transition_illegal_returns_400(client: TestClient) -> None:
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf)["id"]
    resp = client.post(
        f"{PROC}/{pid}/transition", json={"status": "ARCHIVED"}, headers={"If-Match": "0"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PROCEDURE_STATUS_INVALID"


def test_delete_v1_draft_current_succeeds(client: TestClient) -> None:
    # 纯草稿（v1 DRAFT is_current）：P1 relaxation 允许删除（返回 204）
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf)["id"]
    resp = client.request("DELETE", f"{PROC}/{pid}", json={"reason": "不要了"})
    assert resp.status_code == 204


def test_batch_move_endpoint(client: TestClient) -> None:
    src = _make_leaf(client, name="src", prefix="SR")
    dst = _make_leaf(client, name="dst", prefix="DS")
    pid = _make_procedure(client, src)["id"]
    resp = client.post(f"{PROC}/batch-move", json={"ids": [pid], "target_folder_id": dst})
    assert resp.status_code == 200
    assert resp.json()["moved_ids"] == [pid]
    # code 不变
    assert client.get(f"{PROC}/{pid}").json()["procedure"]["code"] == "SR-00001"


def test_library_endpoint_only_published(client: TestClient) -> None:
    leaf = _make_leaf(client)
    _make_procedure(client, leaf, name="草稿")  # 仍是 DRAFT
    pid = _make_procedure(client, leaf, name="已发布")["id"]
    client.post(f"{PROC}/{pid}/transition", json={"status": "PUBLISHED"}, headers={"If-Match": "0"})

    resp = client.get(f"{PROC}/library")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "PUBLISHED"


def test_batch_delete_endpoint_atomic_on_current(client: TestClient) -> None:
    leaf = _make_leaf(client)
    a = _make_procedure(client, leaf, name="一")["id"]
    b = _make_procedure(client, leaf, name="二")["id"]
    resp = client.post(f"{PROC}/batch-delete", json={"ids": [a, b], "reason": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted_ids"] == []
    assert {f["code"] for f in body["failed"]} == {"PROCEDURE_IS_CURRENT"}


def test_delete_non_current_returns_204(client: TestClient, factory: Factory) -> None:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    old = factory.procedure(leaf.id, is_current=False, status="ARCHIVED", code="QC-00077")
    resp = client.request("DELETE", f"{PROC}/{old.id}", json={"reason": "清理"})
def test_archive_endpoint_full_flow(client: TestClient, db: Session) -> None:
    """端到端：创建程序 → archive → 校验 status + folder。"""
    run_seed(db)
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf, name="要归档的程序")["id"]
    # 先发布
    client.post(f"{PROC}/{pid}/transition", json={"status": "PUBLISHED"}, headers={"If-Match": "0"})
    
    res = client.post(
        f"{PROC}/{pid}/archive",
        json={"reason": "stale—keep for reference"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ARCHIVED"
    # 归档文件夹应该存在且被引用
    assert body["folder_id"] is not None


def test_archive_then_restore_round_trip(client: TestClient, db: Session) -> None:
    """从归档恢复：复用现有 restore 端点。"""
    run_seed(db)
    leaf = _make_leaf(client)
    pid = _make_procedure(client, leaf, name="要测试的程序")["id"]
    # 先发布
    client.post(f"{PROC}/{pid}/transition", json={"status": "PUBLISHED"}, headers={"If-Match": "0"})
    
    # 归档
    client.post(f"{PROC}/{pid}/archive", json={"reason": "stale"})
    
    # 恢复回原 folder
    res = client.post(
        f"{PROC}/{pid}/restore",
        json={"reason": "back", "target_folder_id": leaf}
    )

    assert res.status_code == 200
    body = res.json()
    # restore 创建新 DRAFT、回到原 folder
    assert body["status"] == "DRAFT"
    assert body["folder_id"] == leaf
