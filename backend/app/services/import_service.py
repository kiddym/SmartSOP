"""导入编排（§9.1 / §19 / §25.2 / Q193）。

把 /parse 返回（用户审查后）的 chapters[] 落库为新程序：创建程序骨架 → 递归建
章节树（§19：chapter 标题容器 + content 子节点落成 ProcedureStep kind='content'）
→ 临时图按 sha256 提升为永久 asset 并改写 URL → 整树重算编号 → 重建 asset 引用。
review 节点直接带入草稿。导入前执行严格互斥归一化：正文下沉至相邻子标题。
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import unprocessable
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.schemas.parse import ImportNodeIn
from app.schemas.procedure import LevelOfUse, ProcedureCreate
from app.services import (
    asset_service,
    editor_service,
    numbering_service,
    procedure_service,
    source_docx_service,
)

# import 默认 level_of_use（向导 step5 仅收 name+folder，Q182 必填字段取默认，建后详情面板可改）
_DEFAULT_LEVEL_OF_USE: LevelOfUse = "reference"

_TEMP_SRC_RE = re.compile(r'src="/api/v1/uploads/([^/"]+)/media/([^"]+)"')


def import_procedure(
    db: Session,
    *,
    name: str,
    folder_id: str,
    description: str,
    chapters: list[ImportNodeIn],
    upload_token: str | None = None,
    meta: RequestMeta,
) -> Procedure:
    name = name.strip()
    if not name:
        raise unprocessable("VALIDATION_FAILED", "程序名不能为空", field="name")

    proc = procedure_service.create_procedure(
        db,
        ProcedureCreate(
            folder_id=folder_id,
            name=name,
            level_of_use=_DEFAULT_LEVEL_OF_USE,
            description=description,
        ),
        meta,
    )

    _normalize_for_exclusion(chapters)
    for i, node in enumerate(chapters):
        _create_node(db, proc, node, parent_id=None, parent_level=0, sort_order=i)

    # 客户端可手改树：复用编辑器最终态校验（Q25 互斥 + content 叶子 + 章节 ≤3 级 +
    # 父引用有效 + 环/孤儿）并回写 level（§20.3），防绕过深度/互斥约束。
    editor_service._validate_and_recompute_levels(db, proc.id)
    numbering_service.recompute(db, proc.id)
    asset_service.rebuild_references(db, proc.id)
    source_docx_service.store_from_token(db, procedure_group_id=proc.procedure_group_id, upload_token=upload_token)
    db.flush()
    return proc


def _normalize_for_exclusion(nodes: list[ImportNodeIn]) -> None:
    """保证每个标题节点的直接孩子要么全是子标题、要么全是正文（严格互斥）。
    标题下若同时有正文与子标题，正文下沉为相邻子标题的前置/后置内容块。"""
    for n in nodes:
        _relocate_stray_content(n)
        _normalize_for_exclusion(n.children)


def _relocate_stray_content(node: ImportNodeIn) -> None:
    children = node.children
    if not any(c.content_type == "chapter" for c in children):
        return  # 叶子（纯正文）或纯分组：合法
    new_children: list[ImportNodeIn] = []
    pending_leading: list[ImportNodeIn] = []
    last_chapter: ImportNodeIn | None = None
    for c in children:
        if c.content_type == "chapter":
            if pending_leading:
                c.children = pending_leading + c.children
                pending_leading = []
            new_children.append(c)
            last_chapter = c
        elif last_chapter is None:
            pending_leading.append(c)        # 第一个子标题之前的正文 → 前置
        else:
            last_chapter.children.append(c)  # 某子标题之后的正文 → 该子标题后置
    node.children = new_children


def _create_node(
    db: Session,
    proc: Procedure,
    node: ImportNodeIn,
    *,
    parent_id: str | None,
    parent_level: int,
    sort_order: int,
) -> None:
    if node.content_type == "content":
        content = _promote_temp_urls(db, proc.id, node.rich_content)
        step = ProcedureStep(
            procedure_id=proc.id,
            chapter_id=parent_id,
            kind="content",
            title="",
            content=content,
            input_schema={},
            attachment_marks=[],
            sort_order=sort_order,
            skip_numbering=node.skip_numbering,
        )
        db.add(step)
        db.flush()
        return
    level = parent_level + 1
    row = ProcedureChapter(
        procedure_id=proc.id,
        parent_id=parent_id,
        title=node.title,
        level=level,
        sort_order=sort_order,
        skip_numbering=node.skip_numbering,
        # 护栏：parser 当前只产 unmarked | review（见 app/parser/result.py:26），
        # 且 UI 不再有 chapter→step/content 路径（章节是纯容器，标记模式不触达）。
        # 这条三元当前等价于 node.mark_status，但留着是为了：若未来 parser 扩展或
        # 上游污染输入，dirty 值会被静默夹紧到 unmarked，而非写脏到 DB。
        mark_status="review" if node.mark_status == "review" else "unmarked",
    )
    db.add(row)
    db.flush()
    for j, child in enumerate(node.children):
        _create_node(db, proc, child, parent_id=row.id, parent_level=level, sort_order=j)


def _promote_temp_urls(db: Session, procedure_id: str, html: str) -> str:
    """把 rich_content 内临时图 URL 提升为永久 asset URL（sha256 去重）。"""

    def repl(match: re.Match[str]) -> str:
        token, filename = match.group(1), match.group(2)
        asset = asset_service.promote_temp(db, token, filename, source_meta={"docx_token": token})
        if asset is None:  # 临时图已过期/丢失：原样保留（降级，不阻断导入）
            return match.group(0)
        return f'src="{asset_service.asset_url(procedure_id, asset.id)}"'

    return _TEMP_SRC_RE.sub(repl, html)
