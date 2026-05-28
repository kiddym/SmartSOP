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
