"""统一节点服务(spec §3/§4)。

"转换"= 改 heading_level/kind 一次写。父子关系派生(node_tree),不存。
所有写函数只 flush 不 commit(router 提交);写 ProcedureNode 前过 enforce_node_invariants。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, not_found
from app.services import optimistic_lock
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


# 用户可 patch 的字段白名单。mark_status 不在内:它只由 review 确认动作(batch_update)
# 与 parser 写入,不走通用 patch。
_PATCHABLE = frozenset(
    {"heading_level", "kind", "body", "input_schema", "attachment_marks", "skip_numbering"}
)


def patch_node(
    db: Session, node_id: str, changes: dict[str, Any], *, expected_revision: int
) -> ProcedureNode:
    """单字段更新(spec §3.1)。changes 只允许 _PATCHABLE 的键。"""
    node = _get_node(db, node_id)
    optimistic_lock.verify_revision(node.revision, expected_revision)

    unknown = set(changes) - _PATCHABLE
    if unknown:
        raise bad_request("BAD_FIELD", f"不可更新字段:{sorted(unknown)}")

    new_kind = changes.get("kind", node.kind)
    new_level = changes["heading_level"] if "heading_level" in changes else node.heading_level
    new_schema = changes.get("input_schema", node.input_schema)
    new_marks = changes.get("attachment_marks", node.attachment_marks)
    enforce_node_invariants(new_kind, new_level, new_schema, new_marks)

    for k, v in changes.items():
        setattr(node, k, v)
    optimistic_lock.bump(node)
    db.flush()
    node_numbering.recompute(db, node.procedure_id)
    return node


def create_node(db: Session, procedure_id: str, data: dict[str, Any]) -> ProcedureNode:
    """新建节点,默认追加到末尾(sort_order = 当前 max + _SORT_GAP)。
    data 可含 sort_order 显式指定位置。"""
    kind = data.get("kind", "node")
    heading_level = data.get("heading_level")
    input_schema = data.get("input_schema", {})
    attachment_marks = data.get("attachment_marks", [])
    enforce_node_invariants(kind, heading_level, input_schema, attachment_marks)

    if "sort_order" in data and data["sort_order"] is not None:
        sort_order = data["sort_order"]
    else:
        existing = _active_nodes(db, procedure_id)
        sort_order = (existing[-1].sort_order + _SORT_GAP) if existing else _SORT_GAP

    node = ProcedureNode(
        procedure_id=procedure_id,
        body=data.get("body", ""),
        heading_level=heading_level,
        kind=kind,
        input_schema=input_schema,
        attachment_marks=attachment_marks,
        skip_numbering=data.get("skip_numbering", False),
        mark_status=data.get("mark_status", "unmarked"),
        sort_order=sort_order,
    )
    db.add(node)
    db.flush()
    node_numbering.recompute(db, procedure_id)
    return node


def delete_node(db: Session, node_id: str) -> None:
    """软删单节点。子节点不随删(派生关系,删后自动重派生)。"""
    node = _get_node(db, node_id)
    node.is_active = False
    node.deleted_at = utcnow()
    db.flush()
    node_numbering.recompute(db, node.procedure_id)
