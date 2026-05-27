"""节点类型转换业务逻辑（api-specification §5.4 / 决策 §五 Q1-Q12 / §19）。

转换接口（原子）：
- chapter → step（convert-to-step / convert-root-to-step）：chapter 必须无子节点（Q4 CHAPTER_HAS_CHILDREN）；
  转出 step.content 为空让用户补（§19.3）；父级移除该 chapter 后若仍有其他 chapter 子节点则
  违反 Q25 → SIBLING_TYPE_CONFLICT（Q29）。
- step → chapter（convert-to-chapter）：新 chapter 为原 step.chapter 的子节点；step 正文转入新 chapter
  下一个 kind='content' 内容块步骤；父级移除 step 后若仍有其他 step 则
  违反 Q25 → SIBLING_TYPE_CONFLICT（Q29）。

事务边界：只 flush，不 commit；结构变更 bump 程序 revision。
"""

from __future__ import annotations

from html.parser import HTMLParser

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, not_found
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
    if _chapter_has_children(db, proc.id, ch.id):
        raise bad_request("CHAPTER_HAS_CHILDREN", "章节含子节点，不能转为步骤")
    if _other_chapter_children_count(db, proc.id, ch.parent_id, ch.id) > 0:
        raise bad_request("SIBLING_TYPE_CONFLICT", "同级仍有章节 / 内容块，转换会违反互斥规则")

    step = ProcedureStep(
        procedure_id=proc.id,
        chapter_id=ch.parent_id,
        kind="step",
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
# step → chapter
# --------------------------------------------------------------------------- #
def convert_to_chapter(db: Session, step_id: str, meta: RequestMeta) -> ConversionResult:
    st = _get_step(db, step_id)
    proc = _get_proc_editable(db, st.procedure_id)

    # 内容块（kind='content'）语义上是"无标题正文"，没有 heading 可作为章节标题；
    # UI 上也不暴露此入口（content 与 step 之间的切换走 setStepKind）。直接拒绝。
    if st.kind != "step":
        raise bad_request("CONTENT_BLOCK_NOT_CONVERTIBLE", "内容块不能转换为章节")

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
        title=st.title or "未命名章节",
        sort_order=0,
        level=new_level,
    )
    db.add(chapter)
    db.flush()

    created = [chapter.id]
    body = _compose_step_body(st)
    if body.strip():
        content_step = ProcedureStep(
            procedure_id=proc.id,
            chapter_id=chapter.id,
            kind="content",
            title="",
            content=body,
            input_schema={},
            sort_order=0,
        )
        db.add(content_step)
        db.flush()
        created.append(content_step.id)

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
# chapter → content（融合式标题降级；Q25 同级互斥）
# --------------------------------------------------------------------------- #
def convert_to_content(db: Session, chapter_id: str, meta: RequestMeta) -> ConversionResult:
    """章节降级为内容块。原 title 搬运到新 step.content；chapter 软删。

    校验：
    - 章节无任何子节点（CHAPTER_HAS_CHILDREN）
    - 同级 siblings 不混类型（SIBLING_TYPE_CONFLICT；天然覆盖根 chapter 周围还有 chapter 的场景）
    """
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)

    if _chapter_has_children(db, proc.id, ch.id):
        raise bad_request("CHAPTER_HAS_CHILDREN", "章节含子节点，不能转为内容块")
    if _other_chapter_children_count(db, proc.id, ch.parent_id, ch.id) > 0:
        raise bad_request("SIBLING_TYPE_CONFLICT", "同级仍有章节，转换会违反互斥规则")

    step = ProcedureStep(
        procedure_id=proc.id,
        chapter_id=ch.parent_id,
        kind="content",
        title="",
        content=ch.title,
        input_schema={},
        sort_order=0,
    )
    db.add(step)
    ch.is_active = False
    ch.deleted_at = utcnow()
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=step.id,
        action="chapter-to-content",
        meta=meta,
        old_value={"chapter_id": ch.id, "title": ch.title},
    )
    return ConversionResult(created=[step.id], deleted=[ch.id])


# --------------------------------------------------------------------------- #
# 拆 heading + content（C）
# --------------------------------------------------------------------------- #
def split_title_content(
    db: Session, chapter_id: str, cursor_offset: int, meta: RequestMeta
) -> ConversionResult:
    """在 chapter.title 的 cursor_offset 位置拆为标题 + 内容。

    title 截短到 [:cursor]，[cursor:] 部分作为新 content step 插入 chapter 下首位
    （现有 step 全部 sort_order +1 让出 0 位）。

    校验：
    - 0 < cursor_offset < len(title)（INVALID_CURSOR）
    - title[cursor:] strip 非空（EMPTY_CONTENT）
    """
    ch = _get_chapter(db, chapter_id)
    proc = _get_proc_editable(db, ch.procedure_id)

    title = ch.title or ""
    if cursor_offset <= 0 or cursor_offset >= len(title):
        raise bad_request("INVALID_CURSOR", "拆分点必须严格在标题中间")
    new_content_text = title[cursor_offset:]
    if not new_content_text.strip():
        raise bad_request("EMPTY_CONTENT", "拆出的内容为空")

    new_title = title[:cursor_offset]

    # 已有 step children 全部 sort_order +1（让出 0 位）
    existing_steps = (
        db.execute(
            select(ProcedureStep).where(
                ProcedureStep.chapter_id == ch.id, ProcedureStep.is_active.is_(True)
            )
        )
        .scalars()
        .all()
    )
    for s in existing_steps:
        s.sort_order += 1

    ch.title = new_title
    new_step = ProcedureStep(
        procedure_id=proc.id,
        chapter_id=ch.id,
        kind="content",
        title="",
        content=new_content_text,
        input_schema={},
        sort_order=0,
    )
    db.add(new_step)
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    _audit(
        db,
        proc,
        target_id=new_step.id,
        action="split-title-content",
        meta=meta,
        old_value={"chapter_id": ch.id, "original_title": title, "cursor": cursor_offset},
        new_value={"new_title": new_title, "new_content": new_content_text},
    )
    return ConversionResult(created=[new_step.id], deleted=[])


