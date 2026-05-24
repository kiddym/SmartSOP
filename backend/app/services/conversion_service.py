"""节点类型转换业务逻辑（api-specification §5.4 / 决策 §五 Q1-Q12 / §19）。

转换接口（原子）：
- chapter → step（convert-to-step / convert-root-to-step）：chapter 必须无子节点（Q4 CHAPTER_HAS_CHILDREN）；
  转出 step.content 为空让用户补（§19.3）；父级移除该 chapter 后若仍有其他 chapter/content 子节点则
  违反 Q25 → SIBLING_TYPE_CONFLICT（Q29）。
- content → steps（content-to-steps / batch-content-to-steps）：按 rich_content 顶层 HTML 块拆分（Q5），
  每块一个 step（title 留空 Q10、content=块、input_schema={type:COMMON} Q11）；父级互斥同上。
- step → chapter（convert-to-chapter）：新 chapter 为原 step.chapter 的子节点（§19 调和：chapter 不得有
  rich_content，故 step.content 转入新 chapter 下的一个 content 子节点）；父级移除 step 后若仍有其他 step 则
  违反 Q25 → SIBLING_TYPE_CONFLICT（Q29）。
- chapter → content：§19 后废弃，返 410 CONVERT_TO_CONTENT_DEPRECATED。

事务边界：只 flush，不 commit；结构变更 bump 程序 revision。
"""

from __future__ import annotations

from html.parser import HTMLParser

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, gone, not_found
from app.models.base import utcnow
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.schemas.node import ConversionResult
from app.services import audit_service, numbering_service, optimistic_lock

MAX_DEPTH = 3


# --------------------------------------------------------------------------- #
# 顶层 HTML 块拆分（Q5）
# --------------------------------------------------------------------------- #
# HTML 空元素（无结束标签）：不可计入嵌套深度，否则吞掉其后所有顶层块。
_VOID_TAGS: frozenset[str] = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


class _BlockSplitter(HTMLParser):
    """把富文本拆为顶层 HTML 块：每个顶层块级元素一块；顶层游离内联内容（文本 /
    实体 / 空元素）累积为一块。空元素不计入深度，避免吞掉其后内容。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.blocks: list[str] = []
        self._buf: list[str] = []  # 当前打开的顶层块级元素内容（depth>=1）
        self._loose: list[str] = []  # 顶层游离内联内容（depth==0）

    @staticmethod
    def _fmt_start(tag: str, attrs: list[tuple[str, str | None]], self_closing: bool) -> str:
        parts = [tag]
        for key, value in attrs:
            parts.append(key if value is None else f'{key}="{value}"')
        inner = " ".join(parts)
        return f"<{inner}/>" if self_closing else f"<{inner}>"

    def _emit(self, token: str) -> None:
        (self._buf if self.depth else self._loose).append(token)

    def _flush_loose(self) -> None:
        block = "".join(self._loose).strip()
        if block:
            self.blocks.append(block)
        self._loose = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        token = self._fmt_start(tag, attrs, self_closing=False)
        if tag in _VOID_TAGS:  # 空元素：当作内联，不入栈
            self._emit(token)
            return
        if self.depth == 0:
            self._flush_loose()  # 新顶层块级元素开始，先收口游离内容
        self._buf.append(token)
        self.depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._emit(self._fmt_start(tag, attrs, self_closing=True))

    def handle_endtag(self, tag: str) -> None:
        if self.depth == 0:
            return  # 游离 / 多余的结束标签，忽略
        self.depth -= 1
        self._buf.append(f"</{tag}>")
        if self.depth == 0:
            block = "".join(self._buf).strip()
            if block:
                self.blocks.append(block)
            self._buf = []

    def handle_data(self, data: str) -> None:
        self._emit(data)

    def handle_entityref(self, name: str) -> None:
        self._emit(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._emit(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        if self.depth:
            self._buf.append(f"<!--{data}-->")

    def close(self) -> None:
        super().close()
        self._flush_loose()


def split_top_level_blocks(html: str) -> list[str]:
    """拆分顶层块；无可识别块时回退为整体一块（保证转换非空操作）。"""
    text = html.strip()
    if not text:
        return [""]
    parser = _BlockSplitter()
    parser.feed(text)
    parser.close()
    return parser.blocks if parser.blocks else [text]


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


def _get_step(db: Session, step_id: str) -> ProcedureStep:
    st = db.execute(
        select(ProcedureStep).where(ProcedureStep.id == step_id, ProcedureStep.is_active.is_(True))
    ).scalar_one_or_none()
    if st is None:
        raise not_found("NOT_FOUND", "步骤不存在")
    return st


def _chapter_has_children(db: Session, proc_id: str, chapter_id: str) -> bool:
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


def _other_chapter_children_count(
    db: Session, proc_id: str, parent_id: str | None, exclude_id: str
) -> int:
    rows = db.execute(
        select(ProcedureChapter.id).where(
            ProcedureChapter.procedure_id == proc_id,
            ProcedureChapter.parent_id.is_(parent_id)
            if parent_id is None
            else ProcedureChapter.parent_id == parent_id,
            ProcedureChapter.is_active.is_(True),
            ProcedureChapter.id != exclude_id,
        )
    ).all()
    return len(rows)


def _other_step_count(db: Session, proc_id: str, chapter_id: str | None, exclude_id: str) -> int:
    rows = db.execute(
        select(ProcedureStep.id).where(
            ProcedureStep.procedure_id == proc_id,
            ProcedureStep.chapter_id.is_(chapter_id)
            if chapter_id is None
            else ProcedureStep.chapter_id == chapter_id,
            ProcedureStep.is_active.is_(True),
            ProcedureStep.id != exclude_id,
        )
    ).all()
    return len(rows)


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
# chapter → step
# --------------------------------------------------------------------------- #
def _convert_chapter_to_step_core(
    db: Session,
    proc: Procedure,
    ch: ProcedureChapter,
    *,
    recompute: bool,
    audit: bool,
    meta: RequestMeta,
) -> ProcedureStep:
    if ch.content_type != "chapter":
        raise bad_request("SIBLING_TYPE_CONFLICT", "只有章节节点可转为步骤")
    if _chapter_has_children(db, proc.id, ch.id):
        raise bad_request("CHAPTER_HAS_CHILDREN", "章节含子节点，不能转为步骤")
    if _other_chapter_children_count(db, proc.id, ch.parent_id, ch.id) > 0:
        raise bad_request("SIBLING_TYPE_CONFLICT", "同级仍有章节 / 内容块，转换会违反互斥规则")

    step = ProcedureStep(
        procedure_id=proc.id,
        chapter_id=ch.parent_id,
        title=ch.title,
        content="",  # §19.3 转出空让用户补
        input_schema={"type": "COMMON"},
        sort_order=0,
    )
    db.add(step)
    ch.is_active = False
    ch.deleted_at = utcnow()
    db.flush()
    if recompute:
        numbering_service.recompute(db, proc.id)
        optimistic_lock.bump(proc)
        db.flush()
    if audit:
        _audit(
            db,
            proc,
            target_id=step.id,
            action="convert-to-step",
            meta=meta,
            old_value={"chapter_id": ch.id, "title": ch.title},
        )
    return step


def convert_to_step(db: Session, chapter_id: str, meta: RequestMeta) -> ConversionResult:
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)
    step = _convert_chapter_to_step_core(db, proc, ch, recompute=True, audit=True, meta=meta)
    return ConversionResult(created=[step.id], deleted=[ch.id])


def convert_root_to_step(db: Session, chapter_id: str, meta: RequestMeta) -> ConversionResult:
    ch = _get_chapter(db, chapter_id)
    if ch.parent_id is not None:
        raise bad_request("SIBLING_TYPE_CONFLICT", "该接口仅用于根章节")
    proc = _get_proc_editable(db, ch.procedure_id)
    step = _convert_chapter_to_step_core(db, proc, ch, recompute=True, audit=True, meta=meta)
    return ConversionResult(created=[step.id], deleted=[ch.id])


# --------------------------------------------------------------------------- #
# content → steps
# --------------------------------------------------------------------------- #
def _content_to_steps_core(
    db: Session,
    proc: Procedure,
    content: ProcedureChapter,
    *,
    recompute: bool,
    audit: bool,
    meta: RequestMeta,
) -> list[ProcedureStep]:
    if content.content_type != "content":
        raise bad_request("SIBLING_TYPE_CONFLICT", "只有内容块可拆为步骤")
    if _other_chapter_children_count(db, proc.id, content.parent_id, content.id) > 0:
        raise bad_request("SIBLING_TYPE_CONFLICT", "同级仍有章节 / 内容块，转换会违反互斥规则")

    blocks = split_top_level_blocks(content.rich_content)
    created: list[ProcedureStep] = []
    for i, block in enumerate(blocks):
        step = ProcedureStep(
            procedure_id=proc.id,
            chapter_id=content.parent_id,
            title="",  # Q10 留空让用户填
            content=block,
            input_schema={"type": "COMMON"},  # Q11
            sort_order=i,
        )
        db.add(step)
        created.append(step)
    content.is_active = False
    content.deleted_at = utcnow()
    db.flush()
    if recompute:
        numbering_service.recompute(db, proc.id)
        optimistic_lock.bump(proc)
        db.flush()
    if audit:
        _audit(
            db,
            proc,
            target_id=content.id,
            action="content-to-steps",
            meta=meta,
            old_value={"content_id": content.id},
            new_value={"step_ids": [s.id for s in created], "count": len(created)},
        )
    return created


def content_to_steps(db: Session, chapter_id: str, meta: RequestMeta) -> ConversionResult:
    content = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, content.procedure_id)
    steps = _content_to_steps_core(db, proc, content, recompute=True, audit=True, meta=meta)
    return ConversionResult(created=[s.id for s in steps], deleted=[content.id])


def batch_content_to_steps(
    db: Session, chapter_ids: list[str], meta: RequestMeta
) -> ConversionResult:
    """原子批量拆分：先全量取节点、统一编辑性校验，逐个转换；任一失败由 router 回滚。"""
    seen: set[str] = set()
    nodes: list[ProcedureChapter] = []
    proc: Procedure | None = None
    for cid in chapter_ids:
        if cid in seen:
            continue
        seen.add(cid)
        node = _get_chapter(db, cid)
        if proc is None:
            proc = _get_proc_editable(db, node.procedure_id)
        elif node.procedure_id != proc.id:
            raise bad_request("SIBLING_TYPE_CONFLICT", "批量转换的节点必须属于同一程序")
        nodes.append(node)

    assert proc is not None  # min_length=1 保证
    created: list[str] = []
    deleted: list[str] = []
    for node in nodes:
        steps = _content_to_steps_core(db, proc, node, recompute=False, audit=True, meta=meta)
        created.extend(s.id for s in steps)
        deleted.append(node.id)

    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    return ConversionResult(created=created, deleted=deleted)


# --------------------------------------------------------------------------- #
# step → chapter
# --------------------------------------------------------------------------- #
def convert_to_chapter(db: Session, step_id: str, meta: RequestMeta) -> ConversionResult:
    st = _get_step(db, step_id)
    proc = _get_proc_editable(db, st.procedure_id)

    # 父级（原 step.chapter）移除该 step 后若仍有其他 step → 互斥冲突（Q29）
    if _other_step_count(db, proc.id, st.chapter_id, st.id) > 0:
        raise bad_request("SIBLING_TYPE_CONFLICT", "同级仍有步骤，转换会违反互斥规则")

    parent_id = st.chapter_id
    parent_level = 0
    if parent_id is not None:
        parent = _get_chapter(db, parent_id)
        parent_level = parent.level
    new_level = parent_level + 1
    if new_level > MAX_DEPTH:
        raise bad_request("CHAPTER_DEPTH_EXCEEDED", f"转换后章节嵌套超过 {MAX_DEPTH} 级")

    chapter = ProcedureChapter(
        procedure_id=proc.id,
        parent_id=parent_id,
        content_type="chapter",
        title=st.title or "未命名章节",
        rich_content="",  # §19：chapter 不承载正文
        sort_order=0,
        level=new_level,
    )
    db.add(chapter)
    db.flush()

    created = [chapter.id]
    # §19 调和：step 正文 / 警示转入新 chapter 下的 content 子节点（不入 chapter.rich_content）
    body = _compose_step_body(st)
    if body.strip():
        content_child = ProcedureChapter(
            procedure_id=proc.id,
            parent_id=chapter.id,
            content_type="content",
            title="",
            rich_content=body,
            sort_order=0,
            level=new_level + 1,
        )
        db.add(content_child)
        db.flush()
        created.append(content_child.id)

    st.is_active = False
    st.deleted_at = utcnow()
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=chapter.id,
        action="convert-to-chapter",
        meta=meta,
        old_value={"step_id": st.id, "title": st.title},
    )
    return ConversionResult(created=created, deleted=[st.id])


def _compose_step_body(st: ProcedureStep) -> str:
    """步骤正文即新 content 节点的 rich_content（§19 调和；警示已并入 content）。"""
    return st.content


# --------------------------------------------------------------------------- #
# chapter → content（已废弃）
# --------------------------------------------------------------------------- #
def convert_to_content(db: Session, chapter_id: str, meta: RequestMeta) -> ConversionResult:
    raise gone("CONVERT_TO_CONTENT_DEPRECATED", "该接口在章节模型重构后不再支持")
