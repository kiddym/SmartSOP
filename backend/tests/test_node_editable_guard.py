"""节点写入必须限定当前草稿程序（审计 #5）。"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.services import node_service

# 该套件直接用 db fixture 建租户行（Procedure/ProcedureNode 均 TenantMixin），
# 需最小 tenant 上下文，否则 fail-closed 的 _before_flush 会抛 TenantContextMissingError。
pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def _proc_with_node(db, status: str, is_current: bool = True):
    proc = Procedure(
        procedure_group_id=str(uuid.uuid4()),
        folder_id=str(uuid.uuid4()),
        code="QC-00001",
        name="P",
        level_of_use="reference",
        version=1,
        status=status,
        is_current=is_current,
    )
    db.add(proc)
    db.flush()
    node = ProcedureNode(
        procedure_id=proc.id, body="x", heading_level=1, kind="node", sort_order=1000
    )
    db.add(node)
    db.commit()
    return proc, node


def test_patch_node_on_published_rejected(db):
    _proc, node = _proc_with_node(db, status="PUBLISHED")
    with pytest.raises(HTTPException) as ei:
        node_service.patch_node(db, node.id, {"body": "hacked"}, expected_revision=node.revision)
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "PROCEDURE_READONLY"


def test_patch_node_on_draft_ok(db):
    _proc, node = _proc_with_node(db, status="DRAFT")
    out = node_service.patch_node(db, node.id, {"body": "ok"}, expected_revision=node.revision)
    assert out.body == "ok"
