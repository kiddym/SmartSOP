"""编辑器整批保存（PUT /procedures/{id}，editor-behavior §8/§17.2 / Q154-Q155）。

编辑器把所有修改攒在前端 store，点「保存」时一次性提交：程序级元字段 + 脏节点 upsert +
显式删除列表。新节点带前端临时 id，后端为其分配真实 id 并返回 临时→真实 映射（前端据此换 id）。
单事务、乐观锁（If-Match → revision）；任一校验失败整体回滚（router 不 commit）。

最终态校验（应用全部 upsert/删除后）：Q25 章节∕叶子项互斥（子章节与步骤+内容块互斥；步骤与
内容块可共存）、章节 ≤3 级、内容块=kind='content' 步骤、执行表单 15 型、正文 ≤5 MB。
校验后整树重算编号（§47）。

事务边界：只 flush，不 commit；由 router 提交。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, not_found, payload_too_large, unprocessable
from app.models.base import new_uuid, utcnow
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.schemas.node import FORM_TYPES
from app.schemas.procedure import ProcedureSaveIn
from app.services import audit_service, field_service, numbering_service, optimistic_lock

MAX_DEPTH = 3
CONTENT_MAX_BYTES = 5 * 1024 * 1024


def _get_proc_editable(db: Session, proc_id: str) -> Procedure:
    proc = db.execute(
        select(Procedure).where(Procedure.id == proc_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑")
    return proc


def _content_size_guard(text: str, message: str) -> None:
    if len(text.encode("utf-8")) > CONTENT_MAX_BYTES:
        raise payload_too_large("CONTENT_TOO_LARGE", message)


def _apply_deletes(
    db: Session,
    proc_id: str,
    chapter_ids: list[str],
    step_ids: list[str],
) -> None:
    """软删指定章节（递归整棵子树 + 其下步骤）与步骤。"""
    now = utcnow()
    if chapter_ids:
        all_chapters = list(
            db.execute(
                select(ProcedureChapter).where(
                    ProcedureChapter.procedure_id == proc_id, ProcedureChapter.is_active.is_(True)
                )
            ).scalars()
        )
        by_parent: dict[str | None, list[ProcedureChapter]] = {}
        for ch in all_chapters:
            by_parent.setdefault(ch.parent_id, []).append(ch)
        targets: set[str] = set()
        stack = list(chapter_ids)
        while stack:
            cid = stack.pop()
            if cid in targets:
                continue
            targets.add(cid)
            stack.extend(c.id for c in by_parent.get(cid, []))
        for ch in all_chapters:
            if ch.id in targets:
                ch.is_active = False
                ch.deleted_at = now
        if targets:
            steps = list(
                db.execute(
                    select(ProcedureStep).where(
                        ProcedureStep.chapter_id.in_(targets), ProcedureStep.is_active.is_(True)
                    )
                ).scalars()
            )
            for st in steps:
                st.is_active = False
                st.deleted_at = now
    if step_ids:
        steps = list(
            db.execute(
                select(ProcedureStep).where(
                    ProcedureStep.id.in_(step_ids), ProcedureStep.is_active.is_(True)
                )
            ).scalars()
        )
        for st in steps:
            st.is_active = False
            st.deleted_at = now


def _validate_and_recompute_levels(db: Session, proc_id: str) -> None:
    """应用后最终态校验：父引用有效、Q25 互斥、章节 ≤3 级。同时回写 level。

    Q25（选项3）：同一父节点下，子章节与叶子项（步骤+内容块）互斥；
    步骤（kind='step'）与内容块（kind='content'）之间不互斥，可共存。
    """
    chapters = list(
        db.execute(
            select(ProcedureChapter).where(
                ProcedureChapter.procedure_id == proc_id, ProcedureChapter.is_active.is_(True)
            )
        ).scalars()
    )
    steps = list(
        db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == proc_id, ProcedureStep.is_active.is_(True)
            )
        ).scalars()
    )
    chapter_by_id = {c.id: c for c in chapters}
    by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for ch in chapters:
        by_parent.setdefault(ch.parent_id, []).append(ch)
    steps_by_chapter: dict[str | None, list[ProcedureStep]] = {}
    for st in steps:
        steps_by_chapter.setdefault(st.chapter_id, []).append(st)

    # 父 / 章节引用必须指向 active 的 chapter 容器
    for ch in chapters:
        if ch.parent_id is not None and chapter_by_id.get(ch.parent_id) is None:
            raise bad_request("SIBLING_TYPE_CONFLICT", "章节的父节点无效")
    for st in steps:
        if st.chapter_id is not None and chapter_by_id.get(st.chapter_id) is None:
            raise bad_request("SIBLING_TYPE_CONFLICT", "步骤所属章节无效")

    # Q25：同一 parent 下 子章节 与 叶子项（步骤+内容块）互斥
    parents = set(by_parent) | set(steps_by_chapter)
    for pid in parents:
        if by_parent.get(pid) and steps_by_chapter.get(pid):
            raise bad_request("SIBLING_TYPE_CONFLICT", "同级不能同时存在章节与步骤/内容块")

    # 从根遍历回写 level + 校验章节深度；顺带检测环 / 孤儿
    visited: set[str] = set()

    def walk(parent_id: str | None, level: int) -> None:
        for ch in sorted(by_parent.get(parent_id, []), key=lambda c: (c.sort_order, c.id)):
            if level > MAX_DEPTH:
                raise bad_request("CHAPTER_DEPTH_EXCEEDED", f"章节嵌套不能超过 {MAX_DEPTH} 级")
            ch.level = level
            visited.add(ch.id)
            walk(ch.id, level + 1)

    walk(None, 1)
    if len(visited) != len(chapters):
        raise bad_request("SIBLING_TYPE_CONFLICT", "存在无法从根到达的节点（环或孤儿）")
    db.flush()


def save_procedure(
    db: Session, proc_id: str, data: ProcedureSaveIn, expected_revision: int, meta: RequestMeta
) -> tuple[Procedure, dict[str, str]]:
    proc = _get_proc_editable(db, proc_id)
    optimistic_lock.verify_revision(proc.revision, expected_revision)

    # 自定义字段值校验：草稿保存只校验已填值格式，不强制必填（Q367/Q368）
    field_service.validate_values(db, data.custom_values, require_check=False)

    # 1. 程序级元字段
    proc.name = data.name
    proc.description = data.description
    proc.risk_level = data.risk_level
    proc.quality_level = data.quality_level
    proc.level_of_use = data.level_of_use
    proc.custom_values = data.custom_values
    proc.version_update_notes = data.version_update_notes

    existing_chapters = {
        c.id: c
        for c in db.execute(
            select(ProcedureChapter).where(
                ProcedureChapter.procedure_id == proc.id, ProcedureChapter.is_active.is_(True)
            )
        ).scalars()
    }
    existing_steps = {
        s.id: s
        for s in db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == proc.id, ProcedureStep.is_active.is_(True)
            )
        ).scalars()
    }

    # 2. 删除（在 upsert 前）
    _apply_deletes(db, proc.id, data.deleted_chapter_ids, data.deleted_step_ids)

    # 3. 临时 id → 真实 id 映射
    id_map: dict[str, str] = {}
    for cu in data.chapters:
        if cu.id not in existing_chapters:
            id_map[cu.id] = new_uuid()
    for su in data.steps:
        if su.id not in existing_steps:
            id_map[su.id] = new_uuid()

    def resolve(value: str | None) -> str | None:
        return None if value is None else id_map.get(value, value)

    # 4. 章节 upsert（章节现为纯标题/分组容器，不含 content 字段）
    for cu in data.chapters:
        ch_node = existing_chapters.get(cu.id)
        if ch_node is None:
            ch_node = ProcedureChapter(id=id_map[cu.id], procedure_id=proc.id)
            db.add(ch_node)
        ch_node.parent_id = resolve(cu.parent_id)
        ch_node.title = cu.title
        ch_node.skip_numbering = cu.skip_numbering
        ch_node.sort_order = cu.sort_order

    # 5. 步骤 upsert（含内容块 kind='content'）
    # 内容块跳过表单类型校验，清空 title/input_schema/attachment_marks
    for su in data.steps:
        if su.kind == "step" and su.input_schema.get("type") not in FORM_TYPES:
            raise unprocessable(
                "VALIDATION_FAILED", "无效的执行表单类型", field="input_schema.type"
            )
        _content_size_guard(su.content, "步骤正文超过 5 MB 上限")
        st_node = existing_steps.get(su.id)
        if st_node is None:
            st_node = ProcedureStep(id=id_map[su.id], procedure_id=proc.id)
            db.add(st_node)
        is_content = su.kind == "content"
        st_node.chapter_id = resolve(su.chapter_id)
        st_node.kind = su.kind
        st_node.title = "" if is_content else su.title
        st_node.content = su.content
        st_node.input_schema = {} if is_content else su.input_schema
        st_node.attachment_marks = [] if is_content else su.attachment_marks
        st_node.skip_numbering = su.skip_numbering
        st_node.sort_order = su.sort_order

    db.flush()
    _validate_and_recompute_levels(db, proc.id)
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()

    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="update",
        meta=meta,
        new_value={
            "saved_chapters": len(data.chapters),
            "saved_steps": len(data.steps),
            "deleted_chapters": len(data.deleted_chapter_ids),
            "deleted_steps": len(data.deleted_step_ids),
        },
    )
    return proc, id_map
