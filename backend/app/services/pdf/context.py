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
from app.models.attachment import Attachment
from app.models.field import ProcedureField
from app.models.folder import Folder
from app.models.procedure import Procedure
from app.services import asset_service, node_service


@dataclass
class StepData:
    id: str
    code: str
    title: str
    content: str
    kind: str
    skip_numbering: bool
    input_schema: dict[str, Any]
    attachment_marks: list[dict[str, Any]]


@dataclass
class ChapterData:
    id: str
    title: str
    code: str
    level: int
    skip_numbering: bool
    children: list[ChapterData] = field(default_factory=list)  # 子章节
    steps: list[StepData] = field(default_factory=list)  # 步骤 + 内容块步骤（按 sort_order 混排）


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
    signoff_enabled: bool


@dataclass
class RenderData:
    procedure: ProcedureData
    root_chapters: list[ChapterData]
    root_steps: list[StepData]
    attachments: list[AttachmentData]
    cover_fields: list[FieldData]
    assets: dict[str, tuple[bytes, str]]  # asset_id → (bytes, mime)


# --------------------------------------------------------------------------- #
def _split_first_block(body: str) -> tuple[str, str]:
    """把统一 node 的 body 切成 (首个块级元素的纯文本, 其余 HTML)。
    用于从 body 还原 legacy 的 (title, content) 二分（spec §2.3 标题=body 首块）：
    heading/step 的标题取首块文本；step 正文取其余。解析失败 → ('', 原文当正文)。

    注：rest 经 lxml 序列化，`<br/>` 会被规整为 `<br>`——纯快照层差异，html_render 两者
    同样渲染成 `<br/>`，视觉不受影响。首块的 tail 文本（块间裸文本）不并入 rest——
    body 均由导入/节点写入以 `<p>title</p>+content` 构造、content 为 Tiptap HTML，不产块间裸文本。"""
    if not body or not body.strip():
        return "", ""
    try:
        from lxml import html as lxml_html

        frag = lxml_html.fragment_fromstring(body, create_parent="div")
    except Exception:  # 异常 HTML：无标题，整体当正文
        return "", body
    children = list(frag)
    if not children:  # 无块级子元素（裸文本）：整段当标题
        return (frag.text or "").strip(), ""
    first = children[0]
    title = (first.text_content() or "").strip()
    rest = "".join(lxml_html.tostring(c, encoding="unicode") for c in children[1:])
    return title, rest


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

    rows = node_service.get_nodes(db, proc_id)  # 扁平 + 派生 parent_id/code（B2a 已建 node）

    chapters_by_id: dict[str, ChapterData] = {}
    children_acc: dict[str | None, list[ChapterData]] = {}
    steps_acc: dict[str | None, list[StepData]] = {}
    for r in rows:  # rows 已按 sort_order 升序 → 同父下保持文档序
        if r["heading_level"] is not None:
            cd = ChapterData(
                id=r["id"],
                title=_split_first_block(r["body"])[0],
                code=r["code"],
                level=r["heading_level"],
                skip_numbering=r["skip_numbering"],
            )
            chapters_by_id[r["id"]] = cd
            children_acc.setdefault(r["parent_id"], []).append(cd)
        elif r["kind"] == "step":
            title, content = _split_first_block(r["body"])
            steps_acc.setdefault(r["parent_id"], []).append(
                StepData(
                    id=r["id"],
                    code=r["code"],
                    title=title,
                    content=content,
                    kind="step",
                    skip_numbering=r["skip_numbering"],
                    input_schema=dict(r["input_schema"] or {}),
                    attachment_marks=list(r["attachment_marks"] or []),
                )
            )
        else:  # content 節點：無標題，整體內聯（pdf-content-no-title）
            steps_acc.setdefault(r["parent_id"], []).append(
                StepData(
                    id=r["id"],
                    code=r["code"],
                    title="",
                    content=r["body"],
                    kind="content",
                    skip_numbering=r["skip_numbering"],
                    input_schema={},
                    attachment_marks=[],
                )
            )
    for cid, cd in chapters_by_id.items():
        cd.children = children_acc.get(cid, [])
        cd.steps = steps_acc.get(cid, [])
    root_chapters = children_acc.get(None, [])
    root_steps = steps_acc.get(None, [])

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
            select(Attachment)
            .where(
                Attachment.entity_type == "procedure",
                Attachment.entity_id == proc_id,
                Attachment.is_active.is_(True),
            )
            .order_by(Attachment.sort_order, Attachment.created_at)
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

    # 预取所有富文本里引用的 asset 字节（node body 字段，含内容块步骤）
    htmls: list[str] = [r["body"] for r in rows]
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
        signoff_enabled=proc.signoff_enabled,
    )
    return RenderData(
        procedure=procedure,
        root_chapters=root_chapters,
        root_steps=root_steps,
        attachments=attachments,
        cover_fields=cover_fields,
        assets=assets,
    )
