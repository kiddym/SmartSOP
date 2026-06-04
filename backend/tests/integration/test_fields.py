"""自定义字段端点集成测试（api-specification §5.7）。

覆盖：
  - 创建字段（text / select / number 各一）
  - 列表（含 field_type / status 过滤）
  - options 端点（archived 选项被过滤）
  - 详情
  - 更新（含 key 不可改、field_type 不可改）
  - 软删
  - 批量改 status
  - 批量软删（含全量找不到 → 全不删）
  - reorder
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("_sop_auth")

FIELDS = "/api/v1/procedure-fields"


# --------------------------------------------------------------------------- #
# 辅助
# --------------------------------------------------------------------------- #


def _create_text(client: TestClient, key: str = "work_order", name: str = "工单号") -> dict:
    resp = client.post(
        FIELDS,
        json={"name": name, "key": key, "field_type": "text"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_select(client: TestClient, key: str = "priority", name: str = "优先级") -> dict:
    resp = client.post(
        FIELDS,
        json={
            "name": name,
            "key": key,
            "field_type": "select",
            "options": [
                {"value": "high", "label": "高"},
                {"value": "low", "label": "低"},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_number(client: TestClient, key: str = "quantity", name: str = "数量") -> dict:
    resp = client.post(
        FIELDS,
        json={
            "name": name,
            "key": key,
            "field_type": "number",
            "validation": {"minimum": 0, "maximum": 9999},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# 创建
# --------------------------------------------------------------------------- #


def test_create_text_field(client: TestClient) -> None:
    data = _create_text(client)
    assert data["key"] == "work_order"
    assert data["field_type"] == "text"
    assert data["status"] == "active"
    assert "id" in data


def test_create_select_field(client: TestClient) -> None:
    data = _create_select(client)
    assert data["field_type"] == "select"
    assert len(data["options"]) == 2
    assert data["options"][0]["value"] == "high"


def test_create_number_field(client: TestClient) -> None:
    data = _create_number(client)
    assert data["field_type"] == "number"
    assert data["validation_rules"]["minimum"] == 0
    assert data["validation_rules"]["maximum"] == 9999


def test_create_duplicate_key_409(client: TestClient) -> None:
    _create_text(client, key="dup_key")
    resp = client.post(FIELDS, json={"name": "重复", "key": "dup_key", "field_type": "text"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "FIELD_KEY_DUPLICATE"


def test_create_invalid_key_422(client: TestClient) -> None:
    resp = client.post(FIELDS, json={"name": "坏key", "key": "Bad-Key!", "field_type": "text"})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# 列表
# --------------------------------------------------------------------------- #


def test_list_all(client: TestClient) -> None:
    _create_text(client, key="f1")
    _create_select(client, key="f2")
    rows = client.get(FIELDS).json()
    assert len(rows) == 2


def test_list_filter_field_type(client: TestClient) -> None:
    _create_text(client, key="t1")
    _create_number(client, key="n1")
    rows = client.get(FIELDS, params={"field_type": "text"}).json()
    assert all(r["field_type"] == "text" for r in rows)
    assert len(rows) == 1


def test_list_filter_status(client: TestClient) -> None:
    f1 = _create_text(client, key="s1")
    _create_text(client, key="s2")
    # archive f1
    client.post(f"{FIELDS}/update-status", json={"ids": [f1["id"]], "status": "archived"})

    active = client.get(FIELDS, params={"status": "active"}).json()
    archived = client.get(FIELDS, params={"status": "archived"}).json()
    assert len(active) == 1
    assert len(archived) == 1
    assert active[0]["status"] == "active"
    assert archived[0]["status"] == "archived"


# --------------------------------------------------------------------------- #
# 详情
# --------------------------------------------------------------------------- #


def test_get_detail(client: TestClient) -> None:
    created = _create_text(client)
    resp = client.get(f"{FIELDS}/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_not_found(client: TestClient) -> None:
    resp = client.get(f"{FIELDS}/nonexistent-id")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


# --------------------------------------------------------------------------- #
# options 端点
# --------------------------------------------------------------------------- #


def test_options_returns_active_fields_only(client: TestClient) -> None:
    f_active = _create_text(client, key="opt_a")
    f_archived = _create_text(client, key="opt_b", name="归档字段")
    # archive one field
    client.post(
        f"{FIELDS}/update-status",
        json={"ids": [f_archived["id"]], "status": "archived"},
    )
    opts = client.get(f"{FIELDS}/options").json()
    ids = [o["id"] for o in opts]
    assert f_active["id"] in ids
    assert f_archived["id"] not in ids


def test_options_filters_archived_options(client: TestClient) -> None:
    """archived=True 的选项不应出现在 /options 响应中。"""
    # Create select field with two options
    resp = client.post(
        FIELDS,
        json={
            "name": "状态",
            "key": "opt_status",
            "field_type": "select",
            "options": [
                {"value": "open", "label": "开放"},
                {"value": "closed", "label": "关闭"},
            ],
        },
    )
    field = resp.json()
    # Update: remove 'closed' option (it becomes archived internally)
    upd = client.put(
        f"{FIELDS}/{field['id']}",
        json={
            "name": "状态",
            "options": [{"value": "open", "label": "开放"}],
        },
    )
    assert upd.status_code == 200

    opts = client.get(f"{FIELDS}/options").json()
    target = next(o for o in opts if o["id"] == field["id"])
    # archived 'closed' option must not appear
    option_values = [o["value"] for o in target["options"]]
    assert "open" in option_values
    assert "closed" not in option_values


def test_options_schema(client: TestClient) -> None:
    _create_text(client, key="schema_check")
    opts = client.get(f"{FIELDS}/options").json()
    assert len(opts) == 1
    o = opts[0]
    for key in ("id", "key", "name", "field_type", "required", "options"):
        assert key in o, f"missing key: {key}"


# --------------------------------------------------------------------------- #
# 更新
# --------------------------------------------------------------------------- #


def test_update_name_and_description(client: TestClient) -> None:
    field = _create_text(client)
    resp = client.put(
        f"{FIELDS}/{field['id']}",
        json={"name": "新名称", "description": "更新后的描述"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "新名称"
    assert data["description"] == "更新后的描述"


def test_update_key_immutable(client: TestClient) -> None:
    field = _create_text(client)
    resp = client.put(
        f"{FIELDS}/{field['id']}",
        json={"name": "保持名称", "key": "changed_key"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "FIELD_KEY_IMMUTABLE"


def test_update_field_type_immutable(client: TestClient) -> None:
    field = _create_text(client)
    resp = client.put(
        f"{FIELDS}/{field['id']}",
        json={"name": "保持名称", "field_type": "number"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "FIELD_TYPE_IMMUTABLE"


def test_update_same_key_allowed(client: TestClient) -> None:
    """传入与原来相同的 key 不视为修改，应成功。"""
    field = _create_text(client, key="same_key")
    resp = client.put(
        f"{FIELDS}/{field['id']}",
        json={"name": "更新名称", "key": "same_key"},
    )
    assert resp.status_code == 200


def test_update_not_found(client: TestClient) -> None:
    resp = client.put(f"{FIELDS}/ghost", json={"name": "x"})
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 软删
# --------------------------------------------------------------------------- #


def test_delete_field(client: TestClient) -> None:
    field = _create_text(client)
    resp = client.delete(f"{FIELDS}/{field['id']}")
    assert resp.status_code == 204
    # 列表中不再出现
    rows = client.get(FIELDS).json()
    assert not any(r["id"] == field["id"] for r in rows)
    # 详情 404
    assert client.get(f"{FIELDS}/{field['id']}").status_code == 404


def test_delete_not_found(client: TestClient) -> None:
    resp = client.delete(f"{FIELDS}/ghost")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 批量改 status
# --------------------------------------------------------------------------- #


def test_batch_update_status(client: TestClient) -> None:
    f1 = _create_text(client, key="bs1")
    f2 = _create_text(client, key="bs2")
    _create_text(client, key="bs3")

    resp = client.post(
        f"{FIELDS}/update-status",
        json={"ids": [f1["id"], f2["id"]], "status": "archived"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert set(result["updated_ids"]) == {f1["id"], f2["id"]}

    archived = client.get(FIELDS, params={"status": "archived"}).json()
    assert len(archived) == 2


def test_batch_update_status_nonexistent_ids_ignored(client: TestClient) -> None:
    """不存在的 id 静默跳过，updated_ids 只包含实际更新项。"""
    f1 = _create_text(client, key="bsn1")
    resp = client.post(
        f"{FIELDS}/update-status",
        json={"ids": [f1["id"], "ghost-id"], "status": "archived"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert f1["id"] in result["updated_ids"]
    assert "ghost-id" not in result["updated_ids"]


# --------------------------------------------------------------------------- #
# 批量软删
# --------------------------------------------------------------------------- #


def test_batch_delete(client: TestClient) -> None:
    f1 = _create_text(client, key="bd1")
    f2 = _create_text(client, key="bd2")

    resp = client.post(f"{FIELDS}/batch-delete", json={"ids": [f1["id"], f2["id"]]})
    assert resp.status_code == 200
    result = resp.json()
    assert set(result["deleted_ids"]) == {f1["id"], f2["id"]}
    assert result["failed"] == []

    rows = client.get(FIELDS).json()
    assert len(rows) == 0


def test_batch_delete_any_missing_all_stay(client: TestClient) -> None:
    """任一 id 不存在 → 全部不删（原子性，Q325）。"""
    f1 = _create_text(client, key="bdm1")

    resp = client.post(
        f"{FIELDS}/batch-delete",
        json={"ids": [f1["id"], "nonexistent-id"]},
    )
    assert resp.status_code == 200
    result = resp.json()
    # 未删除任何字段
    assert result["deleted_ids"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["id"] == "nonexistent-id"
    assert result["failed"][0]["code"] == "NOT_FOUND"

    # f1 仍然存在
    assert client.get(f"{FIELDS}/{f1['id']}").status_code == 200


def test_batch_delete_all_missing(client: TestClient) -> None:
    """全量不存在 → 返回 failed 列表，deleted_ids 为空。"""
    resp = client.post(
        f"{FIELDS}/batch-delete",
        json={"ids": ["ghost-1", "ghost-2"]},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["deleted_ids"] == []
    assert len(result["failed"]) == 2


# --------------------------------------------------------------------------- #
# reorder
# --------------------------------------------------------------------------- #


def test_reorder(client: TestClient) -> None:
    f1 = _create_text(client, key="r1")
    f2 = _create_text(client, key="r2")
    f3 = _create_text(client, key="r3")

    # 逆序排列
    resp = client.post(
        f"{FIELDS}/reorder",
        json={"ordered_ids": [f3["id"], f2["id"], f1["id"]]},
    )
    assert resp.status_code == 200
    result = resp.json()
    ids_in_order = [r["id"] for r in result]
    # f3 应排在前面
    assert ids_in_order.index(f3["id"]) < ids_in_order.index(f2["id"])
    assert ids_in_order.index(f2["id"]) < ids_in_order.index(f1["id"])


def test_reorder_missing_ids_skipped(client: TestClient) -> None:
    """不存在的 id 静默跳过，不影响其他字段。"""
    f1 = _create_text(client, key="rm1")
    f2 = _create_text(client, key="rm2")

    resp = client.post(
        f"{FIELDS}/reorder",
        json={"ordered_ids": ["ghost", f2["id"], f1["id"]]},
    )
    assert resp.status_code == 200
    result = resp.json()
    ids_in_order = [r["id"] for r in result]
    assert f2["id"] in ids_in_order
    assert f1["id"] in ids_in_order


# --------------------------------------------------------------------------- #
# PUT full-replace 语义
# --------------------------------------------------------------------------- #


def test_put_full_replace_required_field(client: TestClient) -> None:
    """PUT 是 full-replace：创建 required=True，PUT 时须显式传 required=True 保持。"""
    resp = client.post(
        FIELDS,
        json={"name": "必填字段", "key": "req_field", "field_type": "text", "required": True},
    )
    assert resp.status_code == 201
    fid = resp.json()["id"]
    # 正确的 full PUT 保持 required=True
    upd = client.put(
        f"{FIELDS}/{fid}",
        json={
            "name": "必填字段",
            "required": True,
            "sort_order": 0,
            "show_on_cover": False,
            "description": "",
        },
    )
    assert upd.status_code == 200
    assert upd.json()["required"] is True
