"""章节业务逻辑（api-specification §5.4 / data-model §3.4 / §19 / §47）。

约束：
- 章节为纯标题 / 分组容器（§19 重构：content_type/rich_content 两列已删）；
  内容块已迁至 ProcedureStep（kind='content'），与步骤同表共存。
- Q25 子节点类型互斥：同一 parent 下 {子 chapter} XOR {叶子项=step+content} XOR 空。
- 章节最多 3 级嵌套（C7/Q190 二次修订回 3）；step / content 为叶子。
- 编号 code 全自动整树重算（§47），每次结构变更即时调用 numbering_service（Q310）。
- 仅 is_current=true 且 status=DRAFT 的程序可编辑（Q14，PROCEDURE_READONLY）。

事务边界：本模块只 flush，不 commit；由 router 提交。结构变更 bump 程序 revision（乐观锁基准）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, not_found
from app.models.base import utcnow
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.schemas.node import ChapterCreate, ChapterMoveIn, ChapterUpdate
from app.services import audit_service, numbering_service, optimistic_lock

MAX_DEPTH = 3


# --------------------------------------------------------------------------- #
# 内部工具
# --------------------------------------------------------------------------- #
def _get_proc_editable(db: Session, proc_id: str) -> Procedure:
    proc = db.execute(
        select(Procedure).where(Procedure.id == proc_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑")
    return proc


def _get_chapter(db: Session, chapter_id: str) -> ProcedureChapter:
    ch = db.execute(
        select(ProcedureChapter).where(
            ProcedureChapter.id == chapter_id, ProcedureChapter.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if ch is None:
        raise not_found("NOT_FOUND", "章节不存在")
    return ch


def _chapter_siblings(db: Session, proc_id: str, parent_id: str | None) -> list[ProcedureChapter]:
    """同 parent 下的 active 章节，按 sort_order 排序。"""
    return list(
        db.execute(
            select(ProcedureChapter)
            .where(
                ProcedureChapter.procedure_id == proc_id,
                ProcedureChapter.parent_id.is_(parent_id)
                if parent_id is None
                else ProcedureChapter.parent_id == parent_id,
                ProcedureChapter.is_active.is_(True),
            )
            .order_by(ProcedureChapter.sort_order, ProcedureChapter.id)
        ).scalars()
    )


def _has_step_children(db: Session, proc_id: str, parent_id: str | None) -> bool:
    return (
        db.execute(
            select(ProcedureStep.id).where(
                ProcedureStep.procedure_id == proc_id,
                ProcedureStep.chapter_id.is_(parent_id)
                if parent_id is None
                else ProcedureStep.chapter_id == parent_id,
                ProcedureStep.is_active.is_(True),
            )
        ).first()
        is not None
    )


def _assert_can_hold_chapter_children(db: Session, proc_id: str, parent_id: str | None) -> None:
    """新增子章节前，parent 下不得已有叶子项（step / content，Q25 互斥）。"""
    if _has_step_children(db, proc_id, parent_id):
        raise bad_request("SIBLING_TYPE_CONFLICT", "该位置已有步骤 / 内容块，不能再加章节")


def _resolve_parent(db: Session, proc_id: str, parent_id: str | None) -> ProcedureChapter | None:
    """校验 parent 存在且同程序（章节均为分组容器，可挂子章节）。"""
    if parent_id is None:
        return None
    parent = _get_chapter(db, parent_id)
    if parent.procedure_id != proc_id:
        raise bad_request("SIBLING_TYPE_CONFLICT", "父节点不属于该程序")
    return parent


def _children_map(db: Session, proc_id: str) -> dict[str | None, list[ProcedureChapter]]:
    rows = list(
        db.execute(
            select(ProcedureChapter).where(
                ProcedureChapter.procedure_id == proc_id, ProcedureChapter.is_active.is_(True)
            )
        ).scalars()
    )
    out: dict[str | None, list[ProcedureChapter]] = {}
    for ch in rows:
        out.setdefault(ch.parent_id, []).append(ch)
    return out


def _subtree_chapter_height(cmap: dict[str | None, list[ProcedureChapter]], root_id: str) -> int:
    """以 root 为顶的子树中章节的最大相对深度（root 自身=0）。"""
    best = 0
    for child in cmap.get(root_id, []):
        best = max(best, 1 + _subtree_chapter_height(cmap, child.id))
    return best


def _reassign_levels(
    cmap: dict[str | None, list[ProcedureChapter]], node: ProcedureChapter, level: int
) -> None:
    node.level = level
    for child in cmap.get(node.id, []):
        _reassign_levels(cmap, child, level + 1)


def _normalize_sort(siblings: list[ProcedureChapter]) -> None:
    for i, node in enumerate(siblings):
        node.sort_order = i


def _touch(proc: Procedure) -> None:
    """结构变更后推进程序 revision（乐观锁基准）并刷新 updated_at。"""
    optimistic_lock.bump(proc)


def _audit(
    db: Session,
    proc: Procedure,
    *,
    target_id: str,
    action: str,
    meta: RequestMeta,
    old_value: dict[str, object] | None = None,
    new_value: dict[str, object] | None = None,
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=target_id,
        procedure_group_id=proc.procedure_group_id,
        action=action,
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )


# --------------------------------------------------------------------------- #
# 写操作
# --------------------------------------------------------------------------- #
def create_chapter(db: Session, data: ChapterCreate, meta: RequestMeta) -> ProcedureChapter:
    proc = _get_proc_editable(db, data.procedure_id)
    parent = _resolve_parent(db, proc.id, data.parent_id)
    level = (parent.level + 1) if parent is not None else 1

    if level > MAX_DEPTH:
        raise bad_request("CHAPTER_DEPTH_EXCEEDED", f"章节嵌套不能超过 {MAX_DEPTH} 级")
    _assert_can_hold_chapter_children(db, proc.id, data.parent_id)

    siblings = _chapter_siblings(db, proc.id, data.parent_id)
    sort_order = data.sort_order if data.sort_order is not None else len(siblings)

    node = ProcedureChapter(
        procedure_id=proc.id,
        parent_id=data.parent_id,
        title=data.title,
        skip_numbering=data.skip_numbering,
        sort_order=sort_order,
        level=level,
    )
    db.add(node)
    db.flush()
    numbering_service.recompute(db, proc.id)
    _touch(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=node.id,
        action="create",
        meta=meta,
        new_value={
            "title": node.title,
            "parent_id": node.parent_id,
        },
    )
    return node


def update_chapter(
    db: Session, chapter_id: str, data: ChapterUpdate, meta: RequestMeta
) -> ProcedureChapter:
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)

    before = {"title": ch.title, "skip_numbering": ch.skip_numbering}
    ch.title = data.title
    skip_changed = ch.skip_numbering != data.skip_numbering
    ch.skip_numbering = data.skip_numbering

    db.flush()
    if skip_changed:
        numbering_service.recompute(db, proc.id)
    _touch(proc)
    db.flush()
    after = {"title": ch.title, "skip_numbering": ch.skip_numbering}
    old_value, new_value = audit_service.compute_diff(before, after)
    _audit(
        db,
        proc,
        target_id=ch.id,
        action="update",
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )
    return ch


def toggle_skip_numbering(db: Session, chapter_id: str, meta: RequestMeta) -> ProcedureChapter:
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)
    ch.skip_numbering = not ch.skip_numbering
    db.flush()
    numbering_service.recompute(db, proc.id)
    _touch(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=ch.id,
        action="update",
        meta=meta,
        new_value={"skip_numbering": ch.skip_numbering},
    )
    return ch


def _move_swap(db: Session, chapter_id: str, meta: RequestMeta, *, delta: int) -> ProcedureChapter:
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)
    siblings = _chapter_siblings(db, proc.id, ch.parent_id)
    idx = next((i for i, s in enumerate(siblings) if s.id == ch.id), -1)
    target = idx + delta
    if idx < 0 or target < 0 or target >= len(siblings):
        return ch  # 到顶 / 到底：无操作（前端按钮 disabled）
    other = siblings[target]
    ch.sort_order, other.sort_order = other.sort_order, ch.sort_order
    db.flush()
    numbering_service.recompute(db, proc.id)
    _touch(proc)
    db.flush()
    _audit(
        db, proc, target_id=ch.id, action="move", meta=meta, new_value={"sort_order": ch.sort_order}
    )
    return ch


def move_up(db: Session, chapter_id: str, meta: RequestMeta) -> ProcedureChapter:
    return _move_swap(db, chapter_id, meta, delta=-1)


def move_down(db: Session, chapter_id: str, meta: RequestMeta) -> ProcedureChapter:
    return _move_swap(db, chapter_id, meta, delta=1)


def move_chapter(
    db: Session, chapter_id: str, data: ChapterMoveIn, meta: RequestMeta
) -> ProcedureChapter:
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)
    target_parent_id = data.target_parent_id

    cmap = _children_map(db, proc.id)
    # 循环检测：目标父节点不得为自身或自身子孙
    if target_parent_id is not None:
        forbidden = {ch.id}
        stack = [ch.id]
        while stack:
            cur = stack.pop()
            for child in cmap.get(cur, []):
                forbidden.add(child.id)
                stack.append(child.id)
        if target_parent_id in forbidden:
            raise bad_request("SIBLING_TYPE_CONFLICT", "不能把节点移动到自身或其子孙下")

    parent = _resolve_parent(db, proc.id, target_parent_id)
    base_level = (parent.level + 1) if parent is not None else 1
    # 深度校验：移动后子树最深章节不得超过 MAX_DEPTH
    new_max = base_level + _subtree_chapter_height(cmap, ch.id)
    if new_max > MAX_DEPTH:
        raise bad_request("CHAPTER_DEPTH_EXCEEDED", f"移动后章节嵌套超过 {MAX_DEPTH} 级")
    _assert_can_hold_chapter_children(db, proc.id, target_parent_id)

    old_parent_id = ch.parent_id
    # 从原父链移除并重排
    old_siblings = [s for s in _chapter_siblings(db, proc.id, old_parent_id) if s.id != ch.id]
    _normalize_sort(old_siblings)
    # 插入目标父链
    ch.parent_id = target_parent_id
    new_siblings = [s for s in _chapter_siblings(db, proc.id, target_parent_id) if s.id != ch.id]
    index = min(data.target_index, len(new_siblings))
    new_siblings.insert(index, ch)
    _normalize_sort(new_siblings)
    # 重算层级（移动子树整体平移）
    cmap = _children_map(db, proc.id)
    _reassign_levels(cmap, ch, base_level)

    db.flush()
    numbering_service.recompute(db, proc.id)
    _touch(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=ch.id,
        action="move",
        meta=meta,
        old_value={"parent_id": old_parent_id},
        new_value={"parent_id": target_parent_id, "sort_order": ch.sort_order},
    )
    return ch


def delete_chapter(db: Session, chapter_id: str, meta: RequestMeta) -> None:
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)
    cmap = _children_map(db, proc.id)

    # 收集整棵子树的 chapter id（含自身）
    subtree_ids: list[str] = []
    stack = [ch]
    while stack:
        cur = stack.pop()
        subtree_ids.append(cur.id)
        stack.extend(cmap.get(cur.id, []))

    now = utcnow()
    # 软删子树章节 + 其下步骤
    chapters = list(
        db.execute(select(ProcedureChapter).where(ProcedureChapter.id.in_(subtree_ids))).scalars()
    )
    for node in chapters:
        node.is_active = False
        node.deleted_at = now
    steps = list(
        db.execute(
            select(ProcedureStep).where(
                ProcedureStep.chapter_id.in_(subtree_ids), ProcedureStep.is_active.is_(True)
            )
        ).scalars()
    )
    for st in steps:
        st.is_active = False
        st.deleted_at = now

    db.flush()
    # 原父链重排 + 整树重算
    remaining = _chapter_siblings(db, proc.id, ch.parent_id)
    _normalize_sort(remaining)
    numbering_service.recompute(db, proc.id)
    _touch(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=ch.id,
        action="delete",
        meta=meta,
        old_value={"title": ch.title, "subtree_count": len(subtree_ids)},
    )


# --------------------------------------------------------------------------- #
# 读操作
# --------------------------------------------------------------------------- #
def get_chapter(db: Session, chapter_id: str) -> ProcedureChapter:
    return _get_chapter(db, chapter_id)


def list_chapters(
    db: Session,
    *,
    procedure_id: str | None,
    parent_id: str | None,
    mark_status: str | None,
) -> list[ProcedureChapter]:
    stmt = select(ProcedureChapter).where(ProcedureChapter.is_active.is_(True))
    if procedure_id:
        stmt = stmt.where(ProcedureChapter.procedure_id == procedure_id)
    if parent_id:
        stmt = stmt.where(ProcedureChapter.parent_id == parent_id)
    if mark_status:
        stmt = stmt.where(ProcedureChapter.mark_status == mark_status)
    stmt = stmt.order_by(ProcedureChapter.sort_order, ProcedureChapter.id)
    return list(db.execute(stmt).scalars())
