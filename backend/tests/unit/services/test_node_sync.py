"""node_sync.rebuild_from_legacy 单测（Plan B2a 双写补全）。

用 factory 直接造旧 chapter/step 树，调 rebuild_from_legacy，再用 node_service.get_nodes
断言派生出的统一 ProcedureNode 结构与旧树一致。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import node_service, node_sync
from tests.conftest import Factory


def _proc(factory: Factory) -> str:
    folder = factory.folder()
    return factory.procedure(folder_id=folder.id).id


def test_rebuild_chapters_and_content(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    c1 = factory.chapter(pid, title="目的", parent_id=None, sort_order=0)
    factory.step(pid, chapter_id=c1.id, content="<p>本程序规定...</p>", kind="content", sort_order=0)
    c2 = factory.chapter(pid, title="职责", parent_id=None, sort_order=1)
    c21 = factory.chapter(pid, title="质量部", parent_id=c2.id, sort_order=0)
    factory.step(pid, chapter_id=c21.id, content="<p>归口管理</p>", kind="content", sort_order=0)

    node_sync.rebuild_from_legacy(db, pid)

    nodes = node_service.get_nodes(db, pid)
    assert [(n["heading_level"], n["body"], n["code"]) for n in nodes] == [
        (1, "<p>目的</p>", "1"),
        (None, "<p>本程序规定...</p>", ""),
        (1, "<p>职责</p>", "2"),
        (2, "<p>质量部</p>", "2.1"),
        (None, "<p>归口管理</p>", ""),
    ]
    assert nodes[0]["parent_id"] is None
    assert nodes[2]["parent_id"] is None
    assert nodes[1]["parent_id"] == nodes[0]["id"]
    assert nodes[3]["parent_id"] == nodes[2]["id"]
    assert nodes[4]["parent_id"] == nodes[3]["id"]
    assert [n["sort_order"] for n in nodes] == sorted(n["sort_order"] for n in nodes)


def test_rebuild_step_node_keeps_form(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    c1 = factory.chapter(pid, title="执行", sort_order=0)
    factory.step(
        pid, chapter_id=c1.id, content="<p>填表</p>", kind="step",
        input_schema={"type": "COMMON"}, sort_order=0,
    )

    node_sync.rebuild_from_legacy(db, pid)

    leaf = node_service.get_nodes(db, pid)[1]
    assert leaf["kind"] == "step"
    assert leaf["heading_level"] is None
    assert leaf["body"] == "<p>填表</p>"
    assert leaf["input_schema"] == {"type": "COMMON"}


def test_rebuild_preserves_review_clamps_layer_marks(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    factory.chapter(pid, title="存疑", sort_order=0, mark_status="review")
    factory.chapter(pid, title="层级标记残留", sort_order=1, mark_status="step")

    node_sync.rebuild_from_legacy(db, pid)

    nodes = node_service.get_nodes(db, pid)
    assert nodes[0]["mark_status"] == "review"
    assert nodes[1]["mark_status"] == "unmarked"


def test_rebuild_empty_title_body_empty(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    factory.chapter(pid, title="   ", sort_order=0)
    node_sync.rebuild_from_legacy(db, pid)
    assert node_service.get_nodes(db, pid)[0]["body"] == ""


def test_rebuild_skip_numbering_carried(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    factory.chapter(pid, title="不编号章", sort_order=0, skip_numbering=True)
    node_sync.rebuild_from_legacy(db, pid)
    n = node_service.get_nodes(db, pid)[0]
    assert n["skip_numbering"] is True
    assert n["code"] == ""


def test_rebuild_wipes_stale_nodes(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    factory.node(pid, body="<p>陈旧</p>", heading_level=1, sort_order=999)  # 游离旧 node
    factory.chapter(pid, title="真章", sort_order=0)
    node_sync.rebuild_from_legacy(db, pid)
    assert [n["body"] for n in node_service.get_nodes(db, pid)] == ["<p>真章</p>"]
