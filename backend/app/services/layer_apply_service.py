"""层级标定批量应用 service(spec §3)。

事务性:加载 → walk → 校验 → Phase A → B → C → D → recompute + bump + audit。
任一阶段抛错 → router 层 db.rollback,DB 完全不变。

walk 与 frontend layerMark.ts:computeLayerUpdates 等价(见 layer_walk.py)。
"""

from __future__ import annotations

import html as _html
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.services import audit_service, numbering_service, optimistic_lock
from app.services.layer_walk import LayerRow, compute_layer_updates

LayerRole = Literal["chapter_1", "chapter_2", "chapter_3", "content", "keep"]
MAX_DEPTH = 3


def _try_extract_title_from_body(body: str | None) -> str | None:
    """promote auto-extract 资格判定(spec §2.1):body 是 1 个 <p>,内部纯文本(无子元素 / 无样式),
    长度 ≤ 50 Unicode 码点 → 返回提取的纯文本;任一不满足返回 None。
    HTML 实体(如 &amp;)在 lxml 解析时解码为对应字符。
    """
    if not body or not body.strip():
        return None
    try:
        from lxml import html as lxml_html

        frag = lxml_html.fragment_fromstring(body, create_parent="div")
    except Exception:  # 异常 HTML / 解析失败,保守返回 None
        return None
    children = list(frag)
    if len(children) != 1:
        return None
    p = children[0]
    if p.tag != "p":
        return None
    if list(p):  # <p> 含任何子元素 (<b><i><span><br><img>) → 不算纯文本
        return None
    text = p.text or ""
    if len(text) > 50:
        return None
    if not text.strip():
        return None
    return text


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


def _phase_a_to_chapter(
    db: Session,
    proc: Procedure,
    rows: list[LayerRow],
    updates: dict[str, dict],
) -> dict[str, str]:
    """按文档序执行 to-chapter。返回 leaf_id → new_chapter_id 映射。
    parent_id 解析:若 walk 给的 parent 命中映射(同 batch 先一步升的叶子),
    则替换为对应新 chapter id;否则原样使用(指向现存 chapter 或 null)。"""
    from app.models.base import utcnow

    chapter_map: dict[str, str] = {}
    step_by_id = {
        s.id: s for s in db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == proc.id,
                ProcedureStep.is_active.is_(True),
            )
        ).scalars()
    }
    for row in rows:  # 文档序遍历,保证 map 在被引用前已填充
        u = updates.get(row.id)
        if not u or u["kind"] != "to-chapter":
            continue
        st = step_by_id[row.id]
        resolved_parent = chapter_map.get(u["parent_id"], u["parent_id"])
        new_ch = ProcedureChapter(
            procedure_id=proc.id,
            parent_id=resolved_parent,
            title=st.title or "未命名章节",
            sort_order=u["sort_order"],
            level=u["level"],
        )
        db.add(new_ch)
        db.flush()
        if st.content and st.content.strip():
            child = ProcedureStep(
                procedure_id=proc.id,
                chapter_id=new_ch.id,
                kind="content",
                title="",
                content=st.content,
                input_schema={},
                sort_order=0,
            )
            db.add(child)
            db.flush()
        st.is_active = False
        st.deleted_at = utcnow()
        chapter_map[row.id] = new_ch.id
    return chapter_map


def _has_chapter_children(db: Session, proc_id: str, chapter_id: str) -> bool:
    return db.execute(
        select(ProcedureChapter.id).where(
            ProcedureChapter.procedure_id == proc_id,
            ProcedureChapter.parent_id == chapter_id,
            ProcedureChapter.is_active.is_(True),
        )
    ).first() is not None


def _validate_chapter_children_for_content(
    db: Session, proc_id: str, updates: dict[str, dict]
) -> None:
    """章节标 to-content 时若仍有子章节 → 提前 400 CHAPTER_HAS_CHILDREN。"""
    for node_id, u in updates.items():
        if u["kind"] != "to-content":
            continue
        ch = db.get(ProcedureChapter, node_id)
        if ch is None or not ch.is_active:
            continue
        if _has_chapter_children(db, proc_id, ch.id):
            raise bad_request(
                "CHAPTER_HAS_CHILDREN",
                f"章节 {ch.title or ch.id} 仍含子章节,不可降为内容",
            )


def _phase_b_reorder(
    db: Session, updates: dict[str, dict], chapter_map: dict[str, str]
) -> None:
    """章节重排 / 调级 (in-place UPDATE)。"""
    for node_id, u in updates.items():
        if u["kind"] != "reorder":
            continue
        ch = db.get(ProcedureChapter, node_id)
        if ch is None or not ch.is_active:
            continue
        ch.parent_id = chapter_map.get(u["parent_id"], u["parent_id"])
        ch.sort_order = u["sort_order"]
        ch.level = u["level"]


def _phase_c_to_content(
    db: Session,
    proc: Procedure,
    updates: dict[str, dict],
    chapter_map: dict[str, str],
) -> None:
    """章节降为 content step。校验 CHAPTER_HAS_CHILDREN(后端兜底)。"""
    from app.models.base import utcnow

    for node_id, u in updates.items():
        if u["kind"] != "to-content":
            continue
        ch = db.get(ProcedureChapter, node_id)
        if ch is None or not ch.is_active:
            continue
        if _has_chapter_children(db, proc.id, ch.id):
            raise bad_request("CHAPTER_HAS_CHILDREN", f"章节 {ch.title or ch.id} 仍含子章节,不可降为内容")
        title = ch.title or ""
        body = f"<p>{_html.escape(title)}</p>" if title.strip() else ""
        new_step = ProcedureStep(
            procedure_id=proc.id,
            chapter_id=chapter_map.get(u["parent_id"], u["parent_id"]),
            kind="content",
            title="",
            content=body,
            input_schema={},
            sort_order=u["sort_order"],
        )
        db.add(new_step)
        db.flush()
        ch.is_active = False
        ch.deleted_at = utcnow()


def _phase_d_leaf_reparent(
    db: Session, updates: dict[str, dict], chapter_map: dict[str, str]
) -> None:
    """叶子重挂(保持角色叶子)。已被 Phase A 软删的叶子跳过。"""
    for node_id, u in updates.items():
        if u["kind"] != "leaf-reparent":
            continue
        st = db.get(ProcedureStep, node_id)
        if st is None or not st.is_active:
            continue
        st.chapter_id = chapter_map.get(u["parent_id"], u["parent_id"])
        st.sort_order = u["sort_order"]


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
    _validate_chapter_children_for_content(db, proc.id, updates)
    _validate_q25(updates)
    _validate_depth(updates)

    chapter_map = _phase_a_to_chapter(db, proc, rows, updates)
    _phase_b_reorder(db, updates, chapter_map)
    _phase_c_to_content(db, proc, updates, chapter_map)
    _phase_d_leaf_reparent(db, updates, chapter_map)
    db.flush()

    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()

    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="apply-layer-roles",
        meta=meta,
        old_value={"role_count": len(roles)},
        new_value={"chapter_map": chapter_map},
    )

    return {"chapter_map": chapter_map, "revision": proc.revision}
