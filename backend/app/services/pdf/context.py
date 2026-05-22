"""PDF 渲染数据快照（§59.6·Q364）。

从 SQLAlchemy 取数装配成纯 Python 快照（`RenderData`），渲染层只吃快照、不持有
Session —— 便于在线程池跑硬超时（§59.4·Q362）、不踩 SQLAlchemy 线程边界。
图片 asset 字节在此**预取**入 `assets` 字典，渲染层不再访问 DB。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.attachment import ProcedureAttachment
from app.models.chapter import ProcedureChapter
from app.models.field import ProcedureField
from app.models.folder import Folder
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.services import asset_service


@dataclass
class StepData:
    id: str
    code: str
    title: str
    content: str
    skip_numbering: bool
    input_schema: dict[str, Any]
    note: str
    caution: str
    warning: str
    expected_output: str
    attachment_marks: list[dict[str, Any]]
    require_confirmation: bool


@dataclass
class ChapterData:
    id: str
    content_type: str  # chapter / content
    title: str
    code: str
    level: int
    skip_numbering: bool
    rich_content: str
    children: list[ChapterData] = field(default_factory=list)  # 子 chapter/content（混排）
    steps: list[StepData] = field(default_factory=list)  # 步骤（与 children 互斥，Q25）


@dataclass
class AttachmentData:
    id: str
    file_name: str
    size_bytes: int
    mime_type: str
    created_at: datetime
    description: str
    sort_order: int


@dataclass
class FieldData:
    name: str
    key: str
    field_type: str
    display_value: str  # 已解析（select → label；multi → 逗号 label）


@dataclass
class ProcedureData:
    id: str
    code: str
    name: str
    version: int
    status: str
    level_of_use: str
    risk_level: int
    quality_level: int
    description: str
    custom_values: dict[str, Any]
    version_update_notes: str
    version_change_log: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deprecated_at: datetime | None
    folder_full_path: str


@dataclass
class RenderData:
    procedure: ProcedureData
    root_chapters: list[ChapterData]
    root_steps: list[StepData]
    attachments: list[AttachmentData]
    cover_fields: list[FieldData]
    assets: dict[str, tuple[bytes, str]]  # asset_id → (bytes, mime)


# --------------------------------------------------------------------------- #
def _to_step(s: ProcedureStep) -> StepData:
    return StepData(
        id=s.id,
        code=s.code,
        title=s.title,
        content=s.content,
        skip_numbering=s.skip_numbering,
        input_schema=dict(s.input_schema or {}),
        note=s.note,
        caution=s.caution,
        warning=s.warning,
        expected_output=s.expected_output,
        attachment_marks=list(s.attachment_marks or []),
        require_confirmation=s.require_confirmation,
    )


def _resolve_field_value(fld: ProcedureField, raw: Any) -> str:
    """把存储值解析为封面展示串；空值返回 ''（调用方据此跳过，§3.1/Q257）。"""
    if raw is None or raw == "" or raw == []:
        return ""
    options = {
        str(o.get("value")): str(o.get("label", o.get("value"))) for o in (fld.options or [])
    }
    if fld.field_type in ("select",):
        return options.get(str(raw), str(raw))
    if fld.field_type in ("multi_select", "checkbox"):
        if isinstance(raw, list):
            return "、".join(options.get(str(v), str(v)) for v in raw)
        return options.get(str(raw), str(raw))
    return str(raw)


def _collect_asset_ids(*htmls: str) -> set[str]:
    ids: set[str] = set()
    for html in htmls:
        if html:
            ids |= asset_service.extract_asset_ids(html)
    return ids


def load_render_data(db: Session, proc_id: str) -> RenderData:
    """装配渲染快照；程序不存在 → 404 PROCEDURE_NOT_FOUND（§59.4·Q362 / pdf §13）。"""
    proc = db.execute(
        select(Procedure).where(Procedure.id == proc_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("PROCEDURE_NOT_FOUND", "程序不存在")

    folder = db.get(Folder, proc.folder_id)
    folder_path = folder.full_path if folder is not None else ""

    chapters = list(
        db.execute(
            select(ProcedureChapter)
            .where(ProcedureChapter.procedure_id == proc_id, ProcedureChapter.is_active.is_(True))
            .order_by(ProcedureChapter.sort_order, ProcedureChapter.id)
        ).scalars()
    )
    steps = list(
        db.execute(
            select(ProcedureStep)
            .where(ProcedureStep.procedure_id == proc_id, ProcedureStep.is_active.is_(True))
            .order_by(ProcedureStep.sort_order, ProcedureStep.id)
        ).scalars()
    )

    children_by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for ch in chapters:
        children_by_parent.setdefault(ch.parent_id, []).append(ch)
    steps_by_chapter: dict[str | None, list[ProcedureStep]] = {}
    for st in steps:
        steps_by_chapter.setdefault(st.chapter_id, []).append(st)

    def build_chapter(ch: ProcedureChapter) -> ChapterData:
        node = ChapterData(
            id=ch.id,
            content_type=ch.content_type,
            title=ch.title,
            code=ch.code,
            level=ch.level,
            skip_numbering=ch.skip_numbering,
            rich_content=ch.rich_content,
            children=[build_chapter(c) for c in children_by_parent.get(ch.id, [])],
            steps=[_to_step(s) for s in steps_by_chapter.get(ch.id, [])],
        )
        return node

    root_chapters = [build_chapter(c) for c in children_by_parent.get(None, [])]
    root_steps = [_to_step(s) for s in steps_by_chapter.get(None, [])]

    attachments = [
        AttachmentData(
            id=a.id,
            file_name=a.file_name,
            size_bytes=a.size_bytes,
            mime_type=a.mime_type,
            created_at=a.created_at,
            description=a.description,
            sort_order=a.sort_order,
        )
        for a in db.execute(
            select(ProcedureAttachment)
            .where(
                ProcedureAttachment.procedure_id == proc_id,
                ProcedureAttachment.is_active.is_(True),
            )
            .order_by(ProcedureAttachment.sort_order, ProcedureAttachment.created_at)
        ).scalars()
    ]

    cover_fields: list[FieldData] = []
    for fld in db.execute(
        select(ProcedureField)
        .where(
            ProcedureField.is_active.is_(True),
            ProcedureField.status == "active",
            ProcedureField.show_on_cover.is_(True),
        )
        .order_by(ProcedureField.sort_order)
    ).scalars():
        display = _resolve_field_value(fld, proc.custom_values.get(fld.key))
        if display:
            cover_fields.append(
                FieldData(
                    name=fld.name, key=fld.key, field_type=fld.field_type, display_value=display
                )
            )

    # 预取所有富文本里引用的 asset 字节（content 节点 + step 富文本字段）
    htmls: list[str] = [c.rich_content for c in chapters]
    for s in steps:
        htmls += [s.content, s.note, s.caution, s.warning]
    assets: dict[str, tuple[bytes, str]] = {}
    for aid in _collect_asset_ids(*htmls):
        try:
            assets[aid] = asset_service.get_asset(db, aid)
        except Exception:  # 取不到的图渲染期降级为占位
            continue

    procedure = ProcedureData(
        id=proc.id,
        code=proc.code,
        name=proc.name,
        version=proc.version,
        status=proc.status,
        level_of_use=proc.level_of_use,
        risk_level=proc.risk_level,
        quality_level=proc.quality_level,
        description=proc.description,
        custom_values=dict(proc.custom_values or {}),
        version_update_notes=proc.version_update_notes,
        version_change_log=list(proc.version_change_log or []),
        created_at=proc.created_at,
        updated_at=proc.updated_at,
        archived_at=proc.archived_at,
        deprecated_at=proc.deprecated_at,
        folder_full_path=folder_path,
    )
    return RenderData(
        procedure=procedure,
        root_chapters=root_chapters,
        root_steps=root_steps,
        attachments=attachments,
        cover_fields=cover_fields,
        assets=assets,
    )
