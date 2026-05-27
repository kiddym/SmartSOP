"""层级标定批量应用 service(spec §3)。

事务性:加载 → walk → 校验 → Phase A → B → C → D → recompute + bump + audit。
任一阶段抛错 → router 层 db.rollback,DB 完全不变。

walk 与 frontend layerMark.ts:computeLayerUpdates 等价(见 layer_walk.py)。
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.services import optimistic_lock
from app.services.layer_walk import LayerRow, compute_layer_updates

LayerRole = Literal["chapter_1", "chapter_2", "chapter_3", "content", "keep"]
MAX_DEPTH = 3


def _get_proc_editable(db: Session, procedure_id: str) -> Procedure:
    proc = db.execute(
        select(Procedure).where(Procedure.id == procedure_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise bad_request("PROCEDURE_NOT_FOUND", "程序不存在")
    return proc


def _build_layer_rows(db: Session, procedure_id: str) -> list[LayerRow]:
    """从 DB 按文档序重建 LayerRow 列表(等价 frontend store.layerRows getter)。"""
    chapters = list(
        db.execute(
            select(ProcedureChapter).where(
                ProcedureChapter.procedure_id == procedure_id,
                ProcedureChapter.is_active.is_(True),
            )
        ).scalars()
    )
    steps = list(
        db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == procedure_id,
                ProcedureStep.is_active.is_(True),
            )
        ).scalars()
    )
    ch_by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for c in chapters:
        ch_by_parent.setdefault(c.parent_id, []).append(c)
    st_by_chapter: dict[str | None, list[ProcedureStep]] = {}
    has_leaf: set[str | None] = set()
    for s in steps:
        st_by_chapter.setdefault(s.chapter_id, []).append(s)
        has_leaf.add(s.chapter_id)
    for lst in ch_by_parent.values():
        lst.sort(key=lambda c: (c.sort_order, c.id))
    for lst in st_by_chapter.values():
        lst.sort(key=lambda s: (s.sort_order, s.id))

    rows: list[LayerRow] = []

    def walk(parent: str | None) -> None:
        for c in ch_by_parent.get(parent, []):
            rows.append(
                LayerRow(
                    id=c.id,
                    kind="chapter",
                    level=c.level,
                    has_leaf_children=c.id in has_leaf,
                )
            )
            walk(c.id)
        for s in st_by_chapter.get(parent, []):
            rows.append(
                LayerRow(
                    id=s.id,
                    kind="content" if s.kind == "content" else "step",
                    level=0,
                    has_leaf_children=False,
                )
            )

    walk(None)
    return rows


def _validate_q25(updates: dict[str, dict]) -> None:
    """按 walk 末态 parent_id 分组——任一组同时含 chapter 类 + leaf 类 → SIBLING_TYPE_CONFLICT。"""
    groups: dict[str | None, dict[str, list[str]]] = {}
    chapter_kinds = {"reorder", "to-chapter"}
    leaf_kinds = {"to-content", "leaf-reparent"}
    for node_id, u in updates.items():
        g = groups.setdefault(u["parent_id"], {"chapters": [], "leaves": []})
        if u["kind"] in chapter_kinds:
            g["chapters"].append(node_id)
        elif u["kind"] in leaf_kinds:
            g["leaves"].append(node_id)
    conflicts = [
        {"parent_id": p, "chapter_children": sorted(g["chapters"]), "leaf_children": sorted(g["leaves"])}
        for p, g in groups.items()
        if g["chapters"] and g["leaves"]
    ]
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SIBLING_TYPE_CONFLICT", "message": "末态同级混合", "conflicts": conflicts},
        )


def _validate_depth(updates: dict[str, dict]) -> None:
    for node_id, u in updates.items():
        if u["kind"] in ("reorder", "to-chapter") and u["level"] > MAX_DEPTH:
            raise bad_request("CHAPTER_DEPTH_EXCEEDED", f"章节嵌套超过 {MAX_DEPTH} 级")


def apply_layer_roles(
    db: Session,
    procedure_id: str,
    *,
    roles: dict[str, LayerRole],
    expected_revision: int,
    meta: RequestMeta,
) -> dict:
    proc = _get_proc_editable(db, procedure_id)
    optimistic_lock.verify_revision(proc.revision, expected_revision)
    rows = _build_layer_rows(db, procedure_id)
    updates = compute_layer_updates(rows, roles)
    _validate_q25(updates)
    _validate_depth(updates)
    # Execution phases A-D come in subsequent tasks.
    return {"chapter_map": {}, "revision": proc.revision}
