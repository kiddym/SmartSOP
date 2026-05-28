"""章节 / 步骤编号引擎（§47 / Q15 / Q27 / Q305-Q311）。

整树重算**内部 code**（render-only 的 L1 `.0` 不入库，由展示层追加，Q305）：

- chapter，skip_numbering=False：参与编号，code = 父 code + '.' + 连续序号；L1 无父前缀 → 'N'。
- chapter，skip_numbering=True：自身 code=''，整个子树静默（code 全空），且**不占序号位**（Q306）。
- step，kind='content'：永远 code=''，**不占序号位**（Q15）。
- step，skip_numbering=False：code = 父 chapter.code + '.' + 同级 step 连续序号；
  根级 step（chapter_id 为空）无前缀 → 'N'；可达 4 段 `1.1.1.1`（Q308）。
- step，skip_numbering=True：code=''，不占序号位。

纯算术、单趟 O(n) 内存遍历（结构变更即时调用，Q310）。事务边界：只改对象 + flush，不 commit。
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import ProcedureChapter
from app.models.step import ProcedureStep


def recompute(db: Session, procedure_id: str) -> None:
    """重算指定程序整棵树的内部 code（仅 is_active 节点参与）。"""
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

    children: dict[str | None, list[ProcedureChapter]] = defaultdict(list)
    for ch in chapters:
        children[ch.parent_id].append(ch)
    steps_by_chapter: dict[str | None, list[ProcedureStep]] = defaultdict(list)
    for st in steps:
        steps_by_chapter[st.chapter_id].append(st)

    for chapter_group in children.values():
        chapter_group.sort(key=lambda c: (c.sort_order, c.id))
    for step_group in steps_by_chapter.values():
        step_group.sort(key=lambda s: (s.sort_order, s.id))

    def number_steps(chapter_id: str | None, prefix: str, silent: bool) -> None:
        seq = 0
        for st in steps_by_chapter.get(chapter_id, []):
            if silent or st.skip_numbering or st.kind == "content":
                st.code = ""
                continue
            seq += 1
            st.code = f"{prefix}.{seq}" if prefix else str(seq)

    def number_chapters(parent_id: str | None, parent_code: str, silent: bool) -> None:
        seq = 0
        for ch in children.get(parent_id, []):
            if silent or ch.skip_numbering:
                ch.code = ""
                number_chapters(ch.id, "", True)
                number_steps(ch.id, "", True)
                continue
            seq += 1
            code = f"{parent_code}.{seq}" if parent_code else str(seq)
            ch.code = code
            number_chapters(ch.id, code, False)
            number_steps(ch.id, code, False)

    number_chapters(None, "", False)
    number_steps(None, "", False)  # 根级 step（与根 chapter 互斥，Q25）
    db.flush()
    # Plan B2a：所有结构写入都经本 recompute 汇聚；在此把旧 chapter/step 树全量镜像成统一
    # ProcedureNode 行，使下游可改读 node（B2b PDF）。临时脚手架，B4 随旧表+本服务一并删。
    # 局部 import：本无循环（node_sync 不 import numbering_service），但避免把 node_sync 及其
    # 依赖传染给所有 import numbering_service 的模块——本钩子是临时脚手架，不值得污染全局依赖。
    from app.services import node_sync
    node_sync.rebuild_from_legacy(db, procedure_id)
