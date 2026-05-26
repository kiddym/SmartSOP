"""步骤业务逻辑（api-specification §5.4 / data-model §3.5 / §40 / §47）。

约束：
- step（含内容块 kind='content'）只能挂在「不含子章节」的 chapter 下，或根级（与根 chapter 互斥，Q25）。
- step 为叶子（无子步骤，Q308）；编号 code = 父 chapter.code + 序号，全自动（§47）。
- 执行表单 15 型（input_schema.type 大写枚举，Q261）；step.content ≤ 5 MB（CONTENT_TOO_LARGE）。
- 仅 is_current=true 且 status=DRAFT 可编辑（PROCEDURE_READONLY）。

事务边界：只 flush，不 commit；结构变更 bump 程序 revision。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, not_found, payload_too_large, unprocessable
from app.models.base import utcnow
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.schemas.node import FORM_TYPES, StepCreate, StepMoveIn, StepUpdate
from app.services import audit_service, numbering_service, optimistic_lock

CONTENT_MAX_BYTES = 5 * 1024 * 1024


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


def _get_step(db: Session, step_id: str) -> ProcedureStep:
    st = db.execute(
        select(ProcedureStep).where(ProcedureStep.id == step_id, ProcedureStep.is_active.is_(True))
    ).scalar_one_or_none()
    if st is None:
        raise not_found("NOT_FOUND", "步骤不存在")
    return st


def _step_siblings(db: Session, proc_id: str, chapter_id: str | None) -> list[ProcedureStep]:
    return list(
        db.execute(
            select(ProcedureStep)
            .where(
                ProcedureStep.procedure_id == proc_id,
                ProcedureStep.chapter_id.is_(chapter_id)
                if chapter_id is None
                else ProcedureStep.chapter_id == chapter_id,
                ProcedureStep.is_active.is_(True),
            )
            .order_by(ProcedureStep.sort_order, ProcedureStep.id)
        ).scalars()
    )


def _assert_can_hold_steps(db: Session, proc_id: str, chapter_id: str | None) -> None:
    """挂 step 前，目标 chapter（或根级）下不得已有 chapter/content 子节点（Q25 互斥）。"""
    has_chapter_children = (
        db.execute(
            select(ProcedureChapter.id).where(
                ProcedureChapter.procedure_id == proc_id,
                ProcedureChapter.parent_id.is_(chapter_id)
                if chapter_id is None
                else ProcedureChapter.parent_id == chapter_id,
                ProcedureChapter.is_active.is_(True),
            )
        ).first()
        is not None
    )
    if has_chapter_children:
        raise bad_request("SIBLING_TYPE_CONFLICT", "该位置已有章节 / 内容块，不能再加步骤")


def _resolve_chapter(db: Session, proc_id: str, chapter_id: str | None) -> None:
    """目标 chapter 必须存在、同程序（章节均为分组容器，可挂叶子项）。"""
    if chapter_id is None:
        return
    parent = db.execute(
        select(ProcedureChapter).where(
            ProcedureChapter.id == chapter_id, ProcedureChapter.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if parent is None:
        raise not_found("NOT_FOUND", "目标章节不存在")
    if parent.procedure_id != proc_id:
        raise bad_request("SIBLING_TYPE_CONFLICT", "目标章节不属于该程序")


def _validate_input_schema(input_schema: dict[str, object]) -> None:
    form_type = input_schema.get("type")
    if form_type not in FORM_TYPES:
        raise unprocessable("VALIDATION_FAILED", "无效的执行表单类型", field="input_schema.type")


def _content_size_guard(content: str) -> None:
    if len(content.encode("utf-8")) > CONTENT_MAX_BYTES:
        raise payload_too_large("CONTENT_TOO_LARGE", "步骤正文超过 5 MB 上限")


def _normalize_sort(siblings: list[ProcedureStep]) -> None:
    for i, st in enumerate(siblings):
        st.sort_order = i


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
def create_step(db: Session, data: StepCreate, meta: RequestMeta) -> ProcedureStep:
    proc = _get_proc_editable(db, data.procedure_id)
    _resolve_chapter(db, proc.id, data.chapter_id)
    _assert_can_hold_steps(db, proc.id, data.chapter_id)
    # content 块无执行表单，input_schema={} 是合法状态；与 editor_service 批量保存路径对齐。
    if data.kind == "step":
        _validate_input_schema(data.input_schema)
    _content_size_guard(data.content)

    siblings = _step_siblings(db, proc.id, data.chapter_id)
    sort_order = data.sort_order if data.sort_order is not None else len(siblings)

    st = ProcedureStep(
        procedure_id=proc.id,
        chapter_id=data.chapter_id,
        kind=data.kind,
        title=data.title,
        content=data.content,
        input_schema=data.input_schema,
        attachment_marks=data.attachment_marks,
        skip_numbering=data.skip_numbering,
        sort_order=sort_order,
    )
    db.add(st)
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=st.id,
        action="create",
        meta=meta,
        new_value={"title": st.title, "chapter_id": st.chapter_id},
    )
    return st


def update_step(db: Session, step_id: str, data: StepUpdate, meta: RequestMeta) -> ProcedureStep:
    st = _get_step(db, step_id)
    proc = _get_proc_editable(db, st.procedure_id)
    # content 块无执行表单，input_schema={} 是合法状态；与 editor_service 批量保存路径对齐。
    if data.kind == "step":
        _validate_input_schema(data.input_schema)
    _content_size_guard(data.content)

    before = {
        "title": st.title,
        "skip_numbering": st.skip_numbering,
        "type": st.input_schema.get("type"),
    }
    skip_changed = st.skip_numbering != data.skip_numbering
    st.kind = data.kind
    st.title = data.title
    st.content = data.content
    st.input_schema = data.input_schema
    st.attachment_marks = data.attachment_marks
    st.skip_numbering = data.skip_numbering

    db.flush()
    if skip_changed:
        numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    after = {
        "title": st.title,
        "skip_numbering": st.skip_numbering,
        "type": st.input_schema.get("type"),
    }
    old_value, new_value = audit_service.compute_diff(before, after)
    _audit(
        db,
        proc,
        target_id=st.id,
        action="update",
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )
    return st


def toggle_skip_numbering(db: Session, step_id: str, meta: RequestMeta) -> ProcedureStep:
    st = _get_step(db, step_id)
    proc = _get_proc_editable(db, st.procedure_id)
    st.skip_numbering = not st.skip_numbering
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=st.id,
        action="update",
        meta=meta,
        new_value={"skip_numbering": st.skip_numbering},
    )
    return st


def _move_swap(db: Session, step_id: str, meta: RequestMeta, *, delta: int) -> ProcedureStep:
    st = _get_step(db, step_id)
    proc = _get_proc_editable(db, st.procedure_id)
    siblings = _step_siblings(db, proc.id, st.chapter_id)
    idx = next((i for i, s in enumerate(siblings) if s.id == st.id), -1)
    target = idx + delta
    if idx < 0 or target < 0 or target >= len(siblings):
        return st
    other = siblings[target]
    st.sort_order, other.sort_order = other.sort_order, st.sort_order
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db, proc, target_id=st.id, action="move", meta=meta, new_value={"sort_order": st.sort_order}
    )
    return st


def move_up(db: Session, step_id: str, meta: RequestMeta) -> ProcedureStep:
    return _move_swap(db, step_id, meta, delta=-1)


def move_down(db: Session, step_id: str, meta: RequestMeta) -> ProcedureStep:
    return _move_swap(db, step_id, meta, delta=1)


def move_step(db: Session, step_id: str, data: StepMoveIn, meta: RequestMeta) -> ProcedureStep:
    st = _get_step(db, step_id)
    proc = _get_proc_editable(db, st.procedure_id)
    target_chapter_id = data.target_chapter_id
    _resolve_chapter(db, proc.id, target_chapter_id)
    _assert_can_hold_steps(db, proc.id, target_chapter_id)

    old_chapter_id = st.chapter_id
    old_siblings = [s for s in _step_siblings(db, proc.id, old_chapter_id) if s.id != st.id]
    _normalize_sort(old_siblings)
    st.chapter_id = target_chapter_id
    new_siblings = [s for s in _step_siblings(db, proc.id, target_chapter_id) if s.id != st.id]
    index = min(data.target_index, len(new_siblings))
    new_siblings.insert(index, st)
    _normalize_sort(new_siblings)

    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=st.id,
        action="move",
        meta=meta,
        old_value={"chapter_id": old_chapter_id},
        new_value={"chapter_id": target_chapter_id, "sort_order": st.sort_order},
    )
    return st


def delete_step(db: Session, step_id: str, meta: RequestMeta) -> None:
    st = _get_step(db, step_id)
    proc = _get_proc_editable(db, st.procedure_id)
    st.is_active = False
    st.deleted_at = utcnow()
    db.flush()
    remaining = _step_siblings(db, proc.id, st.chapter_id)
    _normalize_sort(remaining)
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(db, proc, target_id=st.id, action="delete", meta=meta, old_value={"title": st.title})


# --------------------------------------------------------------------------- #
# 读操作
# --------------------------------------------------------------------------- #
def get_step(db: Session, step_id: str) -> ProcedureStep:
    return _get_step(db, step_id)


def list_steps(
    db: Session, *, procedure_id: str | None, chapter_id: str | None
) -> list[ProcedureStep]:
    stmt = select(ProcedureStep).where(ProcedureStep.is_active.is_(True))
    if procedure_id:
        stmt = stmt.where(ProcedureStep.procedure_id == procedure_id)
    if chapter_id:
        stmt = stmt.where(ProcedureStep.chapter_id == chapter_id)
    stmt = stmt.order_by(ProcedureStep.sort_order, ProcedureStep.id)
    return list(db.execute(stmt).scalars())
