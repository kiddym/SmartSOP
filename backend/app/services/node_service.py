"""统一节点服务(spec §3/§4)。

"转换"= 改 heading_level/kind 一次写。父子关系派生(node_tree),不存。
所有写函数只 flush 不 commit(router 提交);写 ProcedureNode 前过 enforce_node_invariants。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, not_found
from app.models.base import utcnow
from app.models.node import ProcedureNode
from app.services import node_numbering
from app.services._invariants import enforce_node_invariants
from app.services.node_tree import build_tree

_SORT_GAP = 1000


def _active_nodes(db: Session, procedure_id: str) -> list[ProcedureNode]:
    return list(
        db.execute(
            select(ProcedureNode)
            .where(
                ProcedureNode.procedure_id == procedure_id,
                ProcedureNode.is_active.is_(True),
            )
            .order_by(ProcedureNode.sort_order, ProcedureNode.id)
        ).scalars()
    )


def _get_node(db: Session, node_id: str) -> ProcedureNode:
    node = db.execute(
        select(ProcedureNode).where(
            ProcedureNode.id == node_id, ProcedureNode.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if node is None:
        raise not_found("NOT_FOUND", "节点不存在")
    return node


def get_nodes(db: Session, procedure_id: str) -> list[dict[str, Any]]:
    """返回扁平 list,每项含派生 parent_id/depth + 持久字段。"""
    rows = _active_nodes(db, procedure_id)
    derived = {tn.id: tn for tn in _walk(build_tree(rows))}
    out: list[dict[str, Any]] = []
    for r in rows:
        tn = derived[r.id]
        out.append(
            {
                "id": r.id,
                "procedure_id": r.procedure_id,
                "sort_order": r.sort_order,
                "heading_level": r.heading_level,
                "kind": r.kind,
                "body": r.body,
                "code": r.code,
                "skip_numbering": r.skip_numbering,
                "input_schema": r.input_schema,
                "attachment_marks": r.attachment_marks,
                "mark_status": r.mark_status,
                "revision": r.revision,
                "parent_id": tn.parent_id,
                "depth": tn.depth,
            }
        )
    return out


def _walk(roots: list) -> list:
    out: list = []

    def rec(nodes: list) -> None:
        for n in nodes:
            out.append(n)
            rec(n.children)

    rec(roots)
    return out
