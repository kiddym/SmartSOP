"""统一节点服务(spec §3/§4)。

"转换"= 改 heading_level/kind 一次写。父子关系派生(node_tree),不存。
所有写函数只 flush 不 commit(router 提交);写 ProcedureNode 前过 enforce_node_invariants。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, not_found, payload_too_large
from app.models.base import utcnow
from app.models.node import ProcedureNode
from app.services import heading_learning_service, node_numbering, optimistic_lock
from app.services._invariants import enforce_node_invariants
from app.services.node_tree import TreeNode, build_tree

_SORT_GAP = 1000

CONTENT_MAX_BYTES = 5 * 1024 * 1024


def _body_size_guard(body: str) -> None:
    if len(body.encode("utf-8")) > CONTENT_MAX_BYTES:
        raise payload_too_large("CONTENT_TOO_LARGE", "节点正文超过 5 MB 上限")


def _learn_from_edit(
    db: Session, node: ProcedureNode, old_level: int | None, old_mark: str
) -> None:
    """采集样式标题校正信号并重聚合动态字典（M3 隐式学习；无来源样式名则 no-op）。"""
    style = heading_learning_service.observe_node_edit(
        db, node, old_level=old_level, old_mark=old_mark
    )
    if style:
        heading_learning_service.reaggregate(db, style)


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
        select(ProcedureNode).where(ProcedureNode.id == node_id, ProcedureNode.is_active.is_(True))
    ).scalar_one_or_none()
    if node is None:
        raise not_found("NOT_FOUND", "节点不存在")
    return node


def _assert_procedure_editable(db: Session, procedure_id: str) -> None:
    """节点写入前置守卫：委托 procedure_service 校验宿主为当前草稿（单一权威，避免判定分叉）。
    该查询同样受租户作用域，跨租户程序 404，故也把节点写入的宿主检查限定在本租户。"""
    from app.services import procedure_service  # 局部导入避免循环

    procedure_service.assert_node_host_editable(db, procedure_id)


def get_nodes(db: Session, procedure_id: str) -> list[dict[str, Any]]:
    """返回扁平 list,每项含派生 parent_id/depth + 持久字段。"""
    rows = _active_nodes(db, procedure_id)
    derived = {tn.id: tn for tn in _walk(build_tree(rows))}  # type: ignore[arg-type]
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
                "source_style_name": r.source_style_name,
                "revision": r.revision,
                "parent_id": tn.parent_id,
                "depth": tn.depth,
            }
        )
    return out


def _walk(roots: list[TreeNode]) -> list[TreeNode]:
    out: list[TreeNode] = []

    def rec(nodes: list[TreeNode]) -> None:
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
    _assert_procedure_editable(db, node.procedure_id)
    optimistic_lock.verify_revision(node.revision, expected_revision)

    unknown = set(changes) - _PATCHABLE
    if unknown:
        raise bad_request("BAD_FIELD", f"不可更新字段:{sorted(unknown)}")

    if "body" in changes:
        _body_size_guard(changes["body"])

    new_kind = changes.get("kind", node.kind)
    new_level = changes.get("heading_level", node.heading_level)
    new_schema = changes.get("input_schema", node.input_schema)
    new_marks = changes.get("attachment_marks", node.attachment_marks)
    enforce_node_invariants(new_kind, new_level, new_schema, new_marks)

    old_level, old_mark = node.heading_level, node.mark_status
    for k, v in changes.items():
        setattr(node, k, v)
    optimistic_lock.bump(node)
    db.flush()
    node_numbering.recompute(db, node.procedure_id)
    _learn_from_edit(db, node, old_level, old_mark)  # M3 隐式学习信号
    return node


def create_node(db: Session, procedure_id: str, data: dict[str, Any]) -> ProcedureNode:
    """新建节点,默认追加到末尾(sort_order = 当前 max + _SORT_GAP)。
    data 可含 sort_order 显式指定位置。"""
    _assert_procedure_editable(db, procedure_id)
    kind = data.get("kind", "node")
    heading_level = data.get("heading_level")
    input_schema = data.get("input_schema", {})
    attachment_marks = data.get("attachment_marks", [])
    enforce_node_invariants(kind, heading_level, input_schema, attachment_marks)
    _body_size_guard(data.get("body", ""))

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
    _assert_procedure_editable(db, node.procedure_id)
    node.is_active = False
    node.deleted_at = utcnow()
    db.flush()
    node_numbering.recompute(db, node.procedure_id)


def batch_update(
    db: Session, procedure_id: str, updates: dict[str, dict[str, Any]]
) -> list[ProcedureNode]:
    """批量改 heading_level/kind 等(多选浮动条 / 取代旧 apply_marks)。
    改动后若节点 mark_status=='review' 则清回 'unmarked'(确认动作,spec §6.4)。
    单事务,任一不变量违反则整体抛错(router 不 commit → 回滚)。"""
    _assert_procedure_editable(db, procedure_id)
    changed: list[ProcedureNode] = []
    observed: list[tuple[ProcedureNode, int | None, str]] = []  # (node, old_level, old_mark) M3
    for node_id, changes in updates.items():
        node = _get_node(db, node_id)
        if node.procedure_id != procedure_id:
            raise bad_request("BAD_NODE", f"节点 {node_id} 不属于本程序")
        unknown = set(changes) - _PATCHABLE
        if unknown:
            raise bad_request("BAD_FIELD", f"不可更新字段:{sorted(unknown)}")
        if "body" in changes:
            _body_size_guard(changes["body"])
        new_kind = changes.get("kind", node.kind)
        new_level = changes.get("heading_level", node.heading_level)
        new_schema = changes.get("input_schema", node.input_schema)
        new_marks = changes.get("attachment_marks", node.attachment_marks)
        enforce_node_invariants(new_kind, new_level, new_schema, new_marks)
        observed.append((node, node.heading_level, node.mark_status))
        for k, v in changes.items():
            setattr(node, k, v)
        if node.mark_status == "review":
            node.mark_status = "unmarked"
        optimistic_lock.bump(node)
        changed.append(node)
    db.flush()
    node_numbering.recompute(db, procedure_id)
    for node, old_level, old_mark in observed:  # M3 隐式学习信号
        _learn_from_edit(db, node, old_level, old_mark)
    return changed


def reorder(db: Session, procedure_id: str, ordered_ids: list[str]) -> None:
    """按 ordered_ids 给本程序所有 active 节点重写 sort_order(gap 序)。
    ordered_ids 必须恰好是本程序当前所有 active 节点 id 的一个排列。"""
    _assert_procedure_editable(db, procedure_id)
    rows = _active_nodes(db, procedure_id)
    existing = {r.id for r in rows}
    if set(ordered_ids) != existing or len(ordered_ids) != len(existing):
        raise bad_request("BAD_REORDER", "reorder 的 id 列表必须恰好是本程序全部 active 节点的排列")
    by_id = {r.id: r for r in rows}
    for i, nid in enumerate(ordered_ids):
        by_id[nid].sort_order = (i + 1) * _SORT_GAP
    db.flush()
    node_numbering.recompute(db, procedure_id)
