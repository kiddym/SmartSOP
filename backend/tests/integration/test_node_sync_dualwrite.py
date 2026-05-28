"""numbering_service.recompute → node 全量重建的汇聚点 hook 集成测试（Plan B2a）。

证明所有结构写入收尾的 numbering_service.recompute 会把旧树镜像成 ProcedureNode：
直接 recompute、HTTP 颗粒度改动（toggle-skip-numbering）、复制（_clone_tree）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import node_service, numbering_service
from tests.conftest import Factory

FOLDER = "/api/v1/folders"
IMPORT = "/api/v1/procedures/import"


def test_recompute_rebuilds_nodes(factory: Factory, db: Session) -> None:
    folder = factory.folder()
    pid = factory.procedure(folder_id=folder.id).id
    factory.chapter(pid, title="目的", sort_order=0)  # 只造旧树，未造 node
    assert node_service.get_nodes(db, pid) == []

    numbering_service.recompute(db, pid)  # 结构写入唯一汇聚点

    nodes = node_service.get_nodes(db, pid)
    assert [(n["heading_level"], n["body"], n["code"]) for n in nodes] == [(1, "<p>目的</p>", "1")]


def test_recompute_resyncs_after_legacy_change(factory: Factory, db: Session) -> None:
    folder = factory.folder()
    pid = factory.procedure(folder_id=folder.id).id
    ch = factory.chapter(pid, title="旧标题", sort_order=0)
    numbering_service.recompute(db, pid)
    assert node_service.get_nodes(db, pid)[0]["body"] == "<p>旧标题</p>"

    ch.title = "新标题"
    db.flush()
    numbering_service.recompute(db, pid)
    assert node_service.get_nodes(db, pid)[0]["body"] == "<p>新标题</p>"


def test_recompute_rebuilds_step_node(factory: Factory, db: Session) -> None:
    folder = factory.folder()
    pid = factory.procedure(folder_id=folder.id).id
    ch = factory.chapter(pid, title="执行", sort_order=0)
    factory.step(pid, chapter_id=ch.id, title="步骤一", sort_order=0,
                 input_schema={"type": "COMMON"})  # kind='step' 默认
    numbering_service.recompute(db, pid)

    step_node = next(n for n in node_service.get_nodes(db, pid) if n["kind"] == "step")
    assert step_node["heading_level"] is None
    assert step_node["code"] == "1.1"  # 父 heading 1 下的步骤连续编号
    assert step_node["input_schema"] == {"type": "COMMON"}


def _leaf(client: TestClient) -> str:
    return client.post(FOLDER, json={"name": "B2a夹", "prefix": "B2A"}).json()["id"]


def test_granular_toggle_resyncs_nodes(client: TestClient) -> None:
    leaf = _leaf(client)
    chapters = [{"title": "目的", "content_type": "chapter", "children": [
        {"content_type": "content", "rich_content": "<p>x</p>"}]}]
    pid = client.post(
        IMPORT, json={"name": "P", "folder_id": leaf, "chapters": chapters}
    ).json()["id"]
    chap_id = client.get(f"/api/v1/procedures/{pid}").json()["chapters"][0]["id"]
    assert client.get(f"/api/v1/procedures/{pid}/nodes").json()[0]["code"] == "1"

    r = client.post(f"/api/v1/chapters/{chap_id}/toggle-skip-numbering")
    assert r.status_code == 200, r.text

    head = client.get(f"/api/v1/procedures/{pid}/nodes").json()[0]
    assert head["skip_numbering"] is True
    assert head["code"] == ""  # 颗粒度改动经 recompute hook 同步到 node


def test_copy_clones_nodes(client: TestClient) -> None:
    leaf = _leaf(client)
    chapters = [{"title": "目的", "content_type": "chapter", "children": [
        {"content_type": "content", "rich_content": "<p>x</p>"}]}]
    src = client.post(
        IMPORT, json={"name": "源", "folder_id": leaf, "chapters": chapters}
    ).json()["id"]

    r = client.post(
        f"/api/v1/procedures/{src}/copy", json={"target_folder_id": leaf, "name": "副本"}
    )
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]

    nodes = client.get(f"/api/v1/procedures/{new_id}/nodes").json()
    assert [(n["heading_level"], n["body"], n["code"]) for n in nodes] == [
        (1, "<p>目的</p>", "1"),
        (None, "<p>x</p>", ""),
    ]
