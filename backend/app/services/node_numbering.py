"""节点编号引擎(从派生树算 code,沿用 numbering_service 语义)。

- heading(heading_level!=None,非 skip):按层级连续编号(1 / 1.1 / 1.1.1)。
- kind='step'(非 skip):在父 heading 下连续编号(父 code + '.' + seq;无父 → seq)。
- 正文(kind='node' 且 heading_level=None):code='' 不占位。
- skip_numbering:自身 code='' 且整个子树静默,且不占序号位。
纯函数 compute_codes(rows)->{id: code};recompute(db, proc_id) 落库。
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.node import ProcedureNode
from app.services.node_tree import TreeNode, build_tree


class NumRow(Protocol):
    id: str
    heading_level: int | None
    kind: str
    skip_numbering: bool


def compute_codes(rows: list[NumRow]) -> dict[str, str]:
    """rows 已按 sort_order 升序。返回 {node_id: code}。"""
    meta = {r.id: r for r in rows}
    roots = build_tree(rows)  # type: ignore[arg-type]
    codes: dict[str, str] = {}

    def walk_children(siblings: list[TreeNode], parent_code: str, silent: bool) -> None:
        # heading 与 step 各自连续编号;两者在同一父下分别计数(沿用旧引擎双计数器)。
        heading_seq = 0
        step_seq = 0
        for tn in siblings:
            r = meta[tn.id]
            node_silent = silent or r.skip_numbering
            if tn.heading_level is not None:
                # heading
                if node_silent:
                    codes[tn.id] = ""
                    walk_children(tn.children, "", True)
                    continue
                heading_seq += 1
                code = f"{parent_code}.{heading_seq}" if parent_code else str(heading_seq)
                codes[tn.id] = code
                walk_children(tn.children, code, False)
            elif r.kind == "step":
                if node_silent:
                    codes[tn.id] = ""
                    continue
                step_seq += 1
                codes[tn.id] = f"{parent_code}.{step_seq}" if parent_code else str(step_seq)
            else:
                # 正文 node:永远不编号
                codes[tn.id] = ""

    walk_children(roots, "", False)
    return codes


def recompute(db: Session, procedure_id: str) -> None:
    """重算指定程序所有 active 节点的 code 并落库(只 flush,不 commit)。"""
    rows = list(
        db.execute(
            select(ProcedureNode)
            .where(
                ProcedureNode.procedure_id == procedure_id,
                ProcedureNode.is_active.is_(True),
            )
            .order_by(ProcedureNode.sort_order, ProcedureNode.id)
        ).scalars()
    )
    codes = compute_codes(rows)  # type: ignore[arg-type]
    for r in rows:
        r.code = codes.get(r.id, "")
    db.flush()
