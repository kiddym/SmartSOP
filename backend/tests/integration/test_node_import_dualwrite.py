"""导入双写 ProcedureNode 集成测试（Plan B1）。

POST /procedures/import 写入用户审查后的树 → 既建旧 chapter/step，又建新
ProcedureNode 行；用 Plan A 的 GET /procedures/{id}/nodes 断言派生结构。
`client` 与导入共享同一 in-memory 引擎（conftest StaticPool）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

FOLDER = "/api/v1/folders"
IMPORT = "/api/v1/procedures/import"


def _leaf(client: TestClient, *, name: str = "B1夹", prefix: str = "B1") -> str:
    return client.post(FOLDER, json={"name": name, "prefix": prefix}).json()["id"]


def test_import_dualwrites_nodes(client: TestClient) -> None:
    leaf = _leaf(client)
    chapters = [
        {"title": "目的", "content_type": "chapter", "children": [
            {"content_type": "content", "rich_content": "<p>本程序规定...</p>"}]},
        {"title": "职责", "content_type": "chapter", "children": [
            {"title": "质量部", "content_type": "chapter", "children": [
                {"content_type": "content", "rich_content": "<p>归口管理</p>"}]}]},
    ]
    resp = client.post(
        IMPORT, json={"name": "记录控制程序", "folder_id": leaf, "chapters": chapters}
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]

    nodes = client.get(f"/api/v1/procedures/{pid}/nodes").json()
    assert [(n["heading_level"], n["body"], n["code"]) for n in nodes] == [
        (1, "<p>目的</p>", "1"),
        (None, "<p>本程序规定...</p>", ""),
        (1, "<p>职责</p>", "2"),
        (2, "<p>质量部</p>", "2.1"),
        (None, "<p>归口管理</p>", ""),
    ]
    # 派生父子（不存 parent_id，GET /nodes 返回派生值）
    assert nodes[0]["parent_id"] is None
    assert nodes[2]["parent_id"] is None  # 职责 也是根
    assert nodes[1]["parent_id"] == nodes[0]["id"]
    assert nodes[3]["parent_id"] == nodes[2]["id"]
    assert nodes[4]["parent_id"] == nodes[3]["id"]
    # sort_order 升序
    assert [n["sort_order"] for n in nodes] == sorted(n["sort_order"] for n in nodes)
    # 旧 chapter/step 路径仍在（双写并存）
    detail = client.get(f"/api/v1/procedures/{pid}").json()
    assert [c["title"] for c in detail["chapters"]] == ["目的", "职责"]


def test_import_carries_review_and_skip(client: TestClient) -> None:
    leaf = _leaf(client, name="B1夹2", prefix="B2")
    chapters = [
        {"title": "存疑章", "content_type": "chapter", "mark_status": "review",
         "skip_numbering": True, "children": [
            {"content_type": "content", "rich_content": "<p>z</p>"}]},
    ]
    resp = client.post(IMPORT, json={"name": "P2", "folder_id": leaf, "chapters": chapters})
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]

    nodes = client.get(f"/api/v1/procedures/{pid}/nodes").json()
    assert len(nodes) == 2  # 标题 + 子 content 都已落库
    head = nodes[0]
    assert head["heading_level"] == 1
    assert head["mark_status"] == "review"
    assert head["skip_numbering"] is True
    assert head["code"] == ""  # skip_numbering → 不编号
    assert nodes[1]["body"] == "<p>z</p>"  # 子 content 内容正确
