"""版本管理端点集成测试（Phase 7 / api-specification §版本管理）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.seed import run_seed

pytestmark = pytest.mark.usefixtures("_sop_auth")

PROC = "/api/v1/procedures"
GROUPS = "/api/v1/procedure-groups"
FOLDER = "/api/v1/folders"


def _leaf(client: TestClient, *, name: str = "叶子", prefix: str = "QC") -> str:
    return client.post(FOLDER, json={"name": name, "prefix": prefix}).json()["id"]


def _create(client: TestClient, folder_id: str, *, name: str = "启动 SOP") -> dict:
    return client.post(
        PROC, json={"folder_id": folder_id, "name": name, "level_of_use": "continuous"}
    ).json()


def _publish(client: TestClient, proc: dict) -> dict:
    resp = client.post(
        f"{PROC}/{proc['id']}/transition",
        json={"status": "PUBLISHED"},
        headers={"If-Match": str(proc["revision"])},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_upgrade_version_endpoint(client: TestClient, db: Session) -> None:
    run_seed(db)
    leaf = _leaf(client)
    proc = _create(client, leaf)
    _publish(client, proc)
    resp = client.post(f"{PROC}/{proc['id']}/upgrade-version")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == 2
    assert body["status"] == "DRAFT"
    assert body["is_current"] is True


def test_discard_draft_returns_new_current(client: TestClient, db: Session) -> None:
    run_seed(db)
    leaf = _leaf(client)
    proc = _create(client, leaf)
    _publish(client, proc)
    upgraded = client.post(f"{PROC}/{proc['id']}/upgrade-version").json()
    # 丢弃 v2 DRAFT → 回到 v1（ARCHIVED）作为 current
    resp = client.request("DELETE", f"{PROC}/{upgraded['id']}", json={"reason": "丢弃"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted_id"] == upgraded["id"]
    assert body["new_current_id"] == proc["id"]
    assert body["new_current_version"] == 1


def test_group_versions_listing(client: TestClient, db: Session) -> None:
    run_seed(db)
    leaf = _leaf(client)
    proc = _create(client, leaf)
    _publish(client, proc)
    client.post(f"{PROC}/{proc['id']}/upgrade-version")
    gid = proc["procedure_group_id"]

    resp = client.get(f"{GROUPS}/{gid}/versions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 2
    assert len(body["items"]) == 2

    only = client.get(f"{GROUPS}/{gid}/versions", params={"count_only": True})
    assert only.json()["count"] == 2
    assert only.json()["items"] == []


def test_copy_endpoint(client: TestClient, db: Session) -> None:
    run_seed(db)
    src_leaf = _leaf(client, name="源", prefix="SRC")
    dst_leaf = _leaf(client, name="目标", prefix="DST")
    src = _create(client, src_leaf, name="原")
    resp = client.post(f"{PROC}/{src['id']}/copy", json={"target_folder_id": dst_leaf})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["procedure_group_id"] != src["procedure_group_id"]
    assert body["version"] == 1
    assert body["code"].startswith("DST-")
    assert body["name"] == "原 (副本)"


def test_deprecate_then_restore(client: TestClient, db: Session) -> None:
    run_seed(db)
    leaf = _leaf(client)
    proc = _create(client, leaf)
    _publish(client, proc)

    dep = client.post(f"{PROC}/{proc['id']}/deprecate", json={"reason": "废弃"})
    assert dep.status_code == 200, dep.text

    preview = client.get(f"{PROC}/{proc['id']}/restore-preview").json()
    assert preview["folder_exists"] is True
    assert preview["version_count"] == 1

    restored = client.post(f"{PROC}/{proc['id']}/restore", json={"reason": "恢复"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "DRAFT"
    assert restored.json()["version"] == 2


def test_deprecated_guard_blocks_transition(client: TestClient, db: Session) -> None:
    run_seed(db)
    leaf = _leaf(client)
    proc = _create(client, leaf)
    _publish(client, proc)
    client.post(f"{PROC}/{proc['id']}/deprecate", json={"reason": "废弃"})
    # deprecated 后再 transition 应被守卫拒绝
    resp = client.post(
        f"{PROC}/{proc['id']}/transition",
        json={"status": "ARCHIVED"},
        headers={"If-Match": "99"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PROCEDURE_DEPRECATED"


def test_delete_group_v1_draft_endpoint(client: TestClient, db: Session) -> None:
    run_seed(db)
    leaf = _leaf(client)
    proc = _create(client, leaf)
    gid = proc["procedure_group_id"]
    resp = client.request("DELETE", f"{GROUPS}/{gid}", json={"reason": "完全删除"})
    assert resp.status_code == 204, resp.text
    # group 已空
    assert client.get(f"{GROUPS}/{gid}/versions").json()["count"] == 0


def test_normal_soft_delete_returns_204(client: TestClient, db: Session) -> None:
    run_seed(db)
    leaf = _leaf(client)
    proc = _create(client, leaf)
    _publish(client, proc)
    upgraded = client.post(f"{PROC}/{proc['id']}/upgrade-version").json()
    # 删除非 current 的 v1（ARCHIVED）→ 普通软删 204
    resp = client.request("DELETE", f"{PROC}/{proc['id']}", json={"reason": "删除历史"})
    assert resp.status_code == 204, resp.text
    # 校验确实是非 current（upgraded 仍在）
    assert client.get(f"{PROC}/{upgraded['id']}").status_code == 200
