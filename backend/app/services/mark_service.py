"""标记模式业务逻辑（决策 §五 Q2/Q3/Q9 / editor-behavior §3）。

mark_status 仅作用于 chapter 节点（step 不参与，Q264）。三态：unmarked / step / content。
「应用标记」= 原子事务（Q9），按 Q2/Q3 语义映射批量转换：

| mark   | 应用结果                                                              |
|--------|----------------------------------------------------------------------|
| step   | 建 ProcedureStep(kind='step')，正文空；删该章节（须为叶子）          |
| content| 建 ProcedureStep(kind='content')，正文取章节标题包成 <p>…</p>；删该章节（须为叶子）|
| review | 不被 apply-marks 触碰                                                |

互斥校验取「应用后的最终状态」（Q29）：某 parent 下只要有子节点转 step/content，则该 parent 的
所有 chapter 子节点必须**全部**转换——否则 parent 将同时含 step 与 chapter，违反 Q25。
失败全部回滚（router 不 commit），mark_status 保持不变；成功后清空相关节点 mark_status。

事务边界：只 flush，不 commit；结构变更 bump 程序 revision。
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
from app.schemas.node import ApplyMarksResult
from app.services import audit_service, numbering_service, optimistic_lock


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
        raise not_found("NOT_FOUND", "节点不存在")
    return ch


def set_mark_status(
    db: Session, chapter_id: str, mark_status: str, meta: RequestMeta
) -> ProcedureChapter:
    """设置单个 chapter 节点的 mark_status（频繁、不记审计 Q122、不 bump revision）。"""
    ch = _get_chapter(db, chapter_id)
    _get_proc_editable(db, ch.procedure_id)
    ch.mark_status = mark_status
    db.flush()
    return ch


def _has_children(db: Session, chapter_id: str) -> bool:
    has_chapter = (
        db.execute(
            select(ProcedureChapter.id).where(
                ProcedureChapter.parent_id == chapter_id, ProcedureChapter.is_active.is_(True)
            )
        ).first()
        is not None
    )
    has_step = (
        db.execute(
            select(ProcedureStep.id).where(
                ProcedureStep.chapter_id == chapter_id, ProcedureStep.is_active.is_(True)
            )
        ).first()
        is not None
    )
    return has_chapter or has_step


def _active_children(db: Session, proc_id: str, parent_id: str | None) -> list[ProcedureChapter]:
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


def apply_marks(db: Session, proc_id: str, meta: RequestMeta) -> ApplyMarksResult:
    proc = _get_proc_editable(db, proc_id)

    # 仅取标记模式产生的 step/content 标记；不碰 'review'（Word 智能解析的持久态）
    marked = list(
        db.execute(
            select(ProcedureChapter).where(
                ProcedureChapter.procedure_id == proc.id,
                ProcedureChapter.is_active.is_(True),
                ProcedureChapter.mark_status.in_(["step", "content"]),
            )
        ).scalars()
    )
    targets = [n for n in marked if n.mark_status in ("step", "content")]

    # 1. 叶子校验：含子节点的章节不能转
    for n in targets:
        if _has_children(db, n.id):
            raise bad_request("CHAPTER_HAS_CHILDREN", f"章节「{n.title}」含子节点，不能转换")

    # 2. 最终态互斥：某 parent 下若有转换，其余未转章节必须为空（否则 chapter+step 混）。
    # review 章节也算遗留 sibling：留它在原地会让该 parent 变成 chapter+step，违反 Q25。
    target_ids = {n.id for n in targets}
    for parent_id in {n.parent_id for n in targets}:
        remaining = [
            c for c in _active_children(db, proc.id, parent_id) if c.id not in target_ids
        ]
        if remaining:
            raise bad_request("SIBLING_TYPE_CONFLICT", "同级仍有未转换的章节，应用会违反互斥规则")

    # 3. 执行
    created: list[str] = []
    deleted: list[str] = []
    now = utcnow()
    by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for n in targets:
        by_parent.setdefault(n.parent_id, []).append(n)

    for parent_id, nodes in by_parent.items():
        nodes.sort(key=lambda c: (c.sort_order, c.id))
        for seq, n in enumerate(nodes):
            if n.mark_status == "step":
                step = ProcedureStep(
                    procedure_id=proc.id,
                    chapter_id=parent_id,
                    kind="step",
                    title=n.title,
                    content="",
                    input_schema={"type": "COMMON"},
                    sort_order=seq,
                )
                action = "convert-to-step"
            else:  # content
                body = f"<p>{_escape(n.title)}</p>" if n.title.strip() else ""
                step = ProcedureStep(
                    procedure_id=proc.id,
                    chapter_id=parent_id,
                    kind="content",
                    title="",
                    content=body,
                    input_schema={},
                    sort_order=seq,
                )
                action = "mark-to-content"
            db.add(step)
            db.flush()
            created.append(step.id)
            _audit(
                db,
                proc,
                target_id=step.id,
                action=action,
                meta=meta,
                old_value={"chapter_id": n.id},
            )
            n.is_active = False
            n.deleted_at = now
            deleted.append(n.id)

    # 4. 清空剩余 active 节点的 mark_status（无操作的标记等）
    for n in marked:
        if n.is_active:
            n.mark_status = "unmarked"

    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    return ApplyMarksResult(created=created, deleted=deleted)


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
