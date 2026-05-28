"""ProcedureNode 服务与不变量单测。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services._invariants import enforce_node_invariants


def test_node_kind_with_input_schema_rejected() -> None:
    with pytest.raises(HTTPException):
        enforce_node_invariants(
            kind="node", heading_level=None, input_schema={"type": "COMMON"}, attachment_marks=[]
        )


def test_step_kind_with_heading_level_rejected() -> None:
    with pytest.raises(HTTPException):
        enforce_node_invariants(
            kind="step", heading_level=2, input_schema={"type": "COMMON"}, attachment_marks=[]
        )


def test_heading_level_zero_rejected() -> None:
    with pytest.raises(HTTPException):
        enforce_node_invariants(
            kind="node", heading_level=0, input_schema={}, attachment_marks=[]
        )


def test_valid_heading_node_ok() -> None:
    enforce_node_invariants(kind="node", heading_level=2, input_schema={}, attachment_marks=[])


def test_valid_content_node_ok() -> None:
    enforce_node_invariants(kind="node", heading_level=None, input_schema={}, attachment_marks=[])


def test_valid_step_ok() -> None:
    enforce_node_invariants(
        kind="step", heading_level=None, input_schema={"type": "COMMON"}, attachment_marks=[]
    )


from app.services import node_numbering, node_service


def _proc(factory):
    folder = factory.folder()
    return factory.procedure(folder_id=folder.id)


def test_get_nodes_returns_sorted_with_derived(factory, db) -> None:
    proc = _proc(factory)
    factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=1)
    factory.node(proc.id, body="<p>x</p>", sort_order=20, heading_level=None)
    node_numbering.recompute(db, proc.id)
    rows = node_service.get_nodes(db, proc.id)
    assert [r["body"] for r in rows] == ["<p>A</p>", "<p>x</p>"]
    assert rows[0]["parent_id"] is None and rows[0]["depth"] == 0 and rows[0]["code"] == "1"
    assert rows[1]["parent_id"] == rows[0]["id"] and rows[1]["depth"] == 1


def test_patch_promote_content_to_heading(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>3.1 质量部</p>", sort_order=10, heading_level=None)
    updated = node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=1)
    assert updated.heading_level == 2
    assert updated.body == "<p>3.1 质量部</p>"  # body 原地不动
    assert updated.revision == 2


def test_patch_demote_heading_to_content(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=2)
    updated = node_service.patch_node(db, n.id, {"heading_level": None}, expected_revision=1)
    assert updated.heading_level is None
    assert updated.body == "<p>A</p>"


def test_patch_roundtrip_strict(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>3.1 X</p>", sort_order=10, heading_level=None)
    node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=1)
    back = node_service.patch_node(db, n.id, {"heading_level": None}, expected_revision=2)
    assert back.heading_level is None and back.body == "<p>3.1 X</p>"


def test_patch_step_with_heading_level_rejected(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="", sort_order=10, kind="step", heading_level=None,
                     input_schema={"type": "COMMON"})
    with pytest.raises(HTTPException):
        node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=1)


def test_patch_revision_conflict(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=None)
    with pytest.raises(HTTPException):
        node_service.patch_node(db, n.id, {"heading_level": 2}, expected_revision=99)


def test_create_node_appends_to_end(factory, db) -> None:
    proc = _proc(factory)
    factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=1)
    created = node_service.create_node(
        db, proc.id, {"body": "<p>new</p>", "heading_level": None, "kind": "node"}
    )
    rows = node_service.get_nodes(db, proc.id)
    assert rows[-1]["id"] == created.id
    assert created.sort_order > 10


def test_delete_node_soft_deletes(factory, db) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=1)
    node_service.delete_node(db, n.id)
    assert n.is_active is False and n.deleted_at is not None
    assert node_service.get_nodes(db, proc.id) == []


def test_batch_update_sets_level_on_many(factory, db) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="<p>a</p>", sort_order=10, heading_level=None)
    b = factory.node(proc.id, body="<p>b</p>", sort_order=20, heading_level=None)
    c = factory.node(proc.id, body="<p>c</p>", sort_order=30, heading_level=None)
    node_service.batch_update(db, proc.id, {a.id: {"heading_level": 3}, b.id: {"heading_level": 3}})
    assert a.heading_level == 3 and b.heading_level == 3 and c.heading_level is None


def test_batch_update_mark_as_step_clears_review(factory, db) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="", sort_order=10, heading_level=1, mark_status="review")
    node_service.batch_update(
        db, proc.id, {a.id: {"kind": "step", "heading_level": None, "input_schema": {"type": "COMMON"}}}
    )
    assert a.kind == "step" and a.heading_level is None and a.mark_status == "unmarked"


def test_reorder_rewrites_sort_order(factory, db) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="<p>a</p>", sort_order=10, heading_level=1)
    b = factory.node(proc.id, body="<p>b</p>", sort_order=20, heading_level=1)
    # 把 b 排到 a 前面
    node_service.reorder(db, proc.id, [b.id, a.id])
    rows = node_service.get_nodes(db, proc.id)
    assert [r["id"] for r in rows] == [b.id, a.id]


def test_reorder_rejects_unknown_node(factory, db) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="<p>a</p>", sort_order=10, heading_level=1)
    with pytest.raises(HTTPException):
        node_service.reorder(db, proc.id, [a.id, "ghost-id"])
