"""patch_node 仅在编号相关字段变更时重算（性能门控）。"""
from __future__ import annotations

import uuid

import pytest

from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.services import node_numbering, node_service

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def _draft_node(db):
    proc = Procedure(
        procedure_group_id=str(uuid.uuid4()), folder_id=str(uuid.uuid4()), code="QC-00001",
        name="P", level_of_use="reference", version=1, status="DRAFT", is_current=True,
    )
    db.add(proc)
    db.flush()
    node = ProcedureNode(
        procedure_id=proc.id, body="x", heading_level=1, kind="node", sort_order=1000
    )
    db.add(node)
    db.commit()
    return node


def test_body_only_patch_skips_recompute(db, monkeypatch):
    node = _draft_node(db)
    calls: list[int] = []
    monkeypatch.setattr(node_numbering, "recompute", lambda *a, **k: calls.append(1))
    node_service.patch_node(db, node.id, {"body": "new body"}, expected_revision=node.revision)
    assert calls == []  # 正文变更不影响编号，不应重算


def test_level_patch_triggers_recompute(db, monkeypatch):
    node = _draft_node(db)
    calls: list[int] = []
    monkeypatch.setattr(node_numbering, "recompute", lambda *a, **k: calls.append(1))
    node_service.patch_node(db, node.id, {"heading_level": 2}, expected_revision=node.revision)
    assert calls == [1]  # 层级变更需重算编号
