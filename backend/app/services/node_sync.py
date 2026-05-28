"""旧 chapter/step 树 → 统一 ProcedureNode 行的全量重建（Plan B2a 双写补全）。

B1 只在导入路径双写 ProcedureNode；编辑器保存、章节/步骤颗粒度增删改/转换、版本 fork
都只写旧 chapter/step。本模块的 rebuild_from_legacy 从某程序当前 active 的旧树前序展开、
**整程序硬删重建** ProcedureNode 行，使 node 始终与旧树一致。因无任何外键指向 node id
（签核/附件/版本均挂 procedure 级，见 B2 调查），全量重建安全。挂在
numbering_service.recompute 末尾这一"所有结构写入唯一汇聚点"，无需逐个 hook 各 mutator。
属 expand 阶段脚手架，B4 删旧表时一并删除。

统一节点模型见 docs/superpowers/specs/2026-05-28-unified-node-model-design.md §2/§7。
"""

from __future__ import annotations

import html

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import ProcedureChapter
from app.models.node import ProcedureNode
from app.models.step import ProcedureStep
from app.services import node_numbering

_SORT_GAP = 1000


def _chapter_body(title: str) -> str:
    """heading 的 body = 标题首段（spec §2.3）；空标题 → 空 body（占位章节）。"""
    title = title.strip()
    return f"<p>{html.escape(title)}</p>" if title else ""


def _clamp_mark_status(value: str) -> str:
    """node mark_status 只有 unmarked | review；旧 step/content 等层级标记态夹紧为 unmarked，
    review（Word 智能解析持久态）保留。"""
    return "review" if value == "review" else "unmarked"


def rebuild_from_legacy(db: Session, procedure_id: str) -> None:
    """从旧 chapter/step 树全量重建该程序的 ProcedureNode 行。

    硬删现有 node 行 → 前序展开旧树（Q25 保证同父下子章节与叶子项互斥，无交错歧义）
    → 按文档序 gap 赋 sort_order 插入 → node_numbering 重算 code。只 flush 不 commit。
    """
    # 1. 硬删现有 node（无外键指向 node id，安全；避免软删累积死行）
    for n in db.execute(
        select(ProcedureNode).where(ProcedureNode.procedure_id == procedure_id)
    ).scalars():
        db.delete(n)

    # 2. 读 active 旧树并按 parent 分组
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
    chapters_by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for ch in chapters:
        chapters_by_parent.setdefault(ch.parent_id, []).append(ch)
    steps_by_chapter: dict[str | None, list[ProcedureStep]] = {}
    for st in steps:
        steps_by_chapter.setdefault(st.chapter_id, []).append(st)

    # 3. 前序展开，全局 gap 序
    seq = 0

    def _next_sort() -> int:
        nonlocal seq
        seq += 1
        return seq * _SORT_GAP

    def walk(parent_chapter_id: str | None, level: int) -> None:
        for ch in sorted(
            chapters_by_parent.get(parent_chapter_id, []), key=lambda c: (c.sort_order, c.id)
        ):
            db.add(
                ProcedureNode(
                    procedure_id=procedure_id,
                    sort_order=_next_sort(),
                    heading_level=level,
                    kind="node",
                    body=_chapter_body(ch.title),
                    skip_numbering=ch.skip_numbering,
                    mark_status=_clamp_mark_status(ch.mark_status),
                )
            )
            walk(ch.id, level + 1)
        for st in sorted(
            steps_by_chapter.get(parent_chapter_id, []), key=lambda s: (s.sort_order, s.id)
        ):
            is_step = st.kind == "step"
            db.add(
                ProcedureNode(
                    procedure_id=procedure_id,
                    sort_order=_next_sort(),
                    heading_level=None,
                    kind="step" if is_step else "node",
                    body=st.content,
                    input_schema=st.input_schema if is_step else {},
                    attachment_marks=st.attachment_marks if is_step else [],
                    skip_numbering=st.skip_numbering,
                    mark_status="unmarked",
                )
            )

    walk(None, 1)
    db.flush()
    node_numbering.recompute(db, procedure_id)
