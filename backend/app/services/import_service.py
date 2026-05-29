"""导入编排（§9.1 / §19 / §25.2）。

把 /parse 返回（用户审查后）的 chapters[] 直接落成 ProcedureNode 行：前序展开导入树，
heading 节点 → heading_level=层级、body=<p>标题</p>；content 节点 → heading_level=None、
body=正文（临时图 URL 提升为永久 asset）。统一 gap 序赋 sort_order → node_numbering 重算 code
→ 重建 asset 引用 → 存源 docx。review 持久态随 heading 带入草稿。
"""

from __future__ import annotations

import html
import re

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import unprocessable
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.schemas.parse import ImportNodeIn
from app.schemas.procedure import LevelOfUse, ProcedureCreate
from app.services import asset_service, node_numbering, procedure_service, source_docx_service

_DEFAULT_LEVEL_OF_USE: LevelOfUse = "reference"
_TEMP_SRC_RE = re.compile(r'src="/api/v1/uploads/([^/"]+)/media/([^"]+)"')
_SORT_GAP = 1000


def _chapter_body(title: str) -> str:
    title = title.strip()
    return f"<p>{html.escape(title)}</p>" if title else ""


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

    seq = 0

    def next_sort() -> int:
        nonlocal seq
        seq += 1
        return seq * _SORT_GAP

    def walk(nodes: list[ImportNodeIn], level: int) -> None:
        for n in nodes:
            if n.content_type == "content":
                db.add(
                    ProcedureNode(
                        procedure_id=proc.id,
                        sort_order=next_sort(),
                        heading_level=None,
                        kind="node",
                        body=_promote_temp_urls(db, proc.id, n.rich_content),
                        skip_numbering=n.skip_numbering,
                        mark_status="unmarked",
                    )
                )
            else:  # chapter（标题容器）
                db.add(
                    ProcedureNode(
                        procedure_id=proc.id,
                        sort_order=next_sort(),
                        heading_level=level,
                        kind="node",
                        body=_chapter_body(n.title),
                        skip_numbering=n.skip_numbering,
                        mark_status="review" if n.mark_status == "review" else "unmarked",
                    )
                )
                walk(n.children, level + 1)

    walk(chapters, 1)
    db.flush()
    node_numbering.recompute(db, proc.id)
    asset_service.rebuild_references(db, proc.id)
    source_docx_service.store_from_token(
        db, procedure_group_id=proc.procedure_group_id, upload_token=upload_token
    )
    db.flush()
    return proc


def _promote_temp_urls(db: Session, procedure_id: str, html_text: str) -> str:
    """把 rich_content 内临时图 URL 提升为永久 asset URL（sha256 去重）。"""

    def repl(match: re.Match[str]) -> str:
        token, filename = match.group(1), match.group(2)
        asset = asset_service.promote_temp(db, token, filename, source_meta={"docx_token": token})
        if asset is None:  # 临时图已过期/丢失：原样保留，降级不阻断导入
            return match.group(0)
        return f'src="{asset_service.asset_url(procedure_id, asset.id)}"'

    return _TEMP_SRC_RE.sub(repl, html_text)
