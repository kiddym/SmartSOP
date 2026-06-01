"""程序附件服务（api-specification §5.5 / §14 / Q113-Q120 / Q228 / Q371）。

承担：附件上传落盘（不去重，每次独立 storage_path，Q119）+ 上限校验（单文件
≤50MB、单版本 ≤30 个、总 ≤200MB，Q120）+ CRUD（软删保留文件）+ 跨版本元数据
复制（upgrade/rollback/copy，storage_path 复用，Q113/Q117）+ 30 天孤儿磁盘清理
（无 active 引用 + 软删 ≥30 天 → 先删文件再硬删行，Q115/Q332/§53.2）。

事务边界：service 只 flush 不 commit（清理任务的逐项提交由 task 负责，§53.2）。
"""

from __future__ import annotations

import mimetypes
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import storage
from app.deps import RequestMeta
from app.errors import app_error, bad_request, not_found
from app.models.attachment import ProcedureAttachment
from app.models.base import new_uuid, utcnow
from app.models.procedure import Procedure
from app.services import audit_service
from app.storage_backends import get_storage_backend

MAX_FILE_BYTES = 50 * 1024 * 1024  # 单文件 ≤50MB（Q120）
MAX_COUNT = 30  # 单 procedure 单版本 ≤30 个（Q120）
MAX_TOTAL_BYTES = 200 * 1024 * 1024  # 单 procedure 单版本总 ≤200MB（Q120）

# 在线预览白名单（Q229）：非白名单返 415，前端不展示预览入口。
PREVIEW_WHITELIST = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}
)
_DEFAULT_MIME = "application/octet-stream"


# --------------------------------------------------------------------------- #
# 内部
# --------------------------------------------------------------------------- #
def _get_proc(db: Session, procedure_id: str) -> Procedure:
    proc = db.execute(
        select(Procedure).where(Procedure.id == procedure_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    return proc


def _assert_editable(proc: Procedure) -> None:
    """附件写约束（Q228）：deprecated → PROCEDURE_DEPRECATED；非当前草稿 → PROCEDURE_READONLY。"""
    if proc.deprecated_at is not None:
        raise bad_request("PROCEDURE_DEPRECATED", "程序已被废止，请先恢复后再操作")
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑附件")


def _resolve_mime(file_name: str, content_type: str | None) -> str:
    """优先用上传声明的 content_type，缺失/通用则按扩展名猜测，最终回退 octet-stream。"""
    if content_type and content_type != _DEFAULT_MIME:
        return content_type
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed or _DEFAULT_MIME


def _active_rows(db: Session, procedure_id: str) -> list[ProcedureAttachment]:
    return list(
        db.execute(
            select(ProcedureAttachment)
            .where(
                ProcedureAttachment.procedure_id == procedure_id,
                ProcedureAttachment.is_active.is_(True),
            )
            .order_by(ProcedureAttachment.sort_order, ProcedureAttachment.created_at)
        ).scalars()
    )


def _bytes_or_404(att: ProcedureAttachment) -> bytes:
    try:
        return get_storage_backend().read(att.storage_path)
    except FileNotFoundError:
        raise not_found("NOT_FOUND", "附件文件已丢失") from None


# --------------------------------------------------------------------------- #
# 读取
# --------------------------------------------------------------------------- #
def list_attachments(db: Session, procedure_id: str) -> list[ProcedureAttachment]:
    """列出某版本的 active 附件（任意状态可读）。程序不存在 → 404。"""
    _get_proc(db, procedure_id)
    return _active_rows(db, procedure_id)


def rows_for(db: Session, procedure_id: str) -> list[ProcedureAttachment]:
    """get_detail 内嵌用：直接查 active 附件行（proc 已由调用方保证存在）。"""
    return _active_rows(db, procedure_id)


def get_or_404(db: Session, attachment_id: str) -> ProcedureAttachment:
    att = db.execute(
        select(ProcedureAttachment).where(
            ProcedureAttachment.id == attachment_id, ProcedureAttachment.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if att is None:
        raise not_found("NOT_FOUND", "附件不存在")
    return att


def download(db: Session, attachment_id: str) -> tuple[bytes, str, str]:
    """下载（不受 deprecated 限制，Q118）。返回 (字节, mime, 原文件名)。"""
    att = get_or_404(db, attachment_id)
    return _bytes_or_404(att), att.mime_type, att.file_name


def preview(db: Session, attachment_id: str) -> tuple[bytes, str]:
    """在线预览（仅白名单类型，Q229）；非白名单 → 415。"""
    att = get_or_404(db, attachment_id)
    if att.mime_type not in PREVIEW_WHITELIST:
        raise app_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "ATTACHMENT_NOT_PREVIEWABLE",
            "该类型不支持在线预览",
        )
    return _bytes_or_404(att), att.mime_type


# --------------------------------------------------------------------------- #
# 写入
# --------------------------------------------------------------------------- #
def upload(
    db: Session,
    procedure_id: str,
    data: bytes,
    file_name: str,
    *,
    content_type: str | None,
    description: str,
    meta: RequestMeta,
) -> ProcedureAttachment:
    """上传附件（仅当前草稿，Q228）+ 上限校验（Q120）+ 落盘 + 审计 upload。"""
    proc = _get_proc(db, procedure_id)
    _assert_editable(proc)

    size = len(data)
    if size > MAX_FILE_BYTES:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "单文件超过 50MB 上限", field="file")
    existing = _active_rows(db, procedure_id)
    if len(existing) + 1 > MAX_COUNT:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "附件数量超过 30 个上限", field="file")
    if sum(a.size_bytes for a in existing) + size > MAX_TOTAL_BYTES:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "附件总大小超过 200MB 上限", field="file")

    name = file_name.strip() or "未命名"
    uid = new_uuid()
    path = storage.attachment_path(uid, Path(name).suffix)
    rel = path.relative_to(storage.storage_root()).as_posix()
    get_storage_backend().write(rel, data)

    att = ProcedureAttachment(
        procedure_id=procedure_id,
        file_name=name,
        storage_path=rel,
        mime_type=_resolve_mime(name, content_type),
        size_bytes=size,
        description=description.strip(),
        sort_order=len(existing),
    )
    db.add(att)
    db.flush()
    audit_service.log_procedure_action(
        db,
        target_id=att.id,
        procedure_group_id=proc.procedure_group_id,
        action="upload",
        meta=meta,
        new_value={"file_name": name, "size_bytes": size},
    )
    return att


def update(
    db: Session,
    attachment_id: str,
    *,
    description: str | None,
    sort_order: int | None,
    meta: RequestMeta,
) -> ProcedureAttachment:
    """改元数据（仅 description / sort_order；仅当前草稿生效、不传播，Q116/Q228）。"""
    att = get_or_404(db, attachment_id)
    proc = _get_proc(db, att.procedure_id)
    _assert_editable(proc)

    before = {"description": att.description, "sort_order": att.sort_order}
    if description is not None:
        att.description = description.strip()
    if sort_order is not None:
        att.sort_order = sort_order
    db.flush()
    after = {"description": att.description, "sort_order": att.sort_order}
    old_value, new_value = audit_service.compute_diff(before, after)
    if new_value:
        audit_service.log_procedure_action(
            db,
            target_id=att.id,
            procedure_group_id=proc.procedure_group_id,
            action="update",
            meta=meta,
            old_value=old_value,
            new_value=new_value,
        )
    return att


def delete(db: Session, attachment_id: str, meta: RequestMeta) -> None:
    """软删（文件保留供其他版本引用，Q114；仅当前草稿，Q228）+ 审计 delete。"""
    att = get_or_404(db, attachment_id)
    proc = _get_proc(db, att.procedure_id)
    _assert_editable(proc)

    att.is_active = False
    att.deleted_at = utcnow()
    db.flush()
    audit_service.log_procedure_action(
        db,
        target_id=att.id,
        procedure_group_id=proc.procedure_group_id,
        action="delete",
        meta=meta,
        old_value={"file_name": att.file_name},
    )


# --------------------------------------------------------------------------- #
# 跨版本元数据复制（Q113 / Q117 / Q371）—— 由 version_flow_service 调用
# --------------------------------------------------------------------------- #
def copy_for_version(db: Session, src_procedure_id: str, dst_procedure_id: str) -> None:
    """复制 src 版本的 active 附件元数据到 dst（新 id、复用 storage_path，物理文件不复制）。"""
    for src in _active_rows(db, src_procedure_id):
        db.add(
            ProcedureAttachment(
                procedure_id=dst_procedure_id,
                file_name=src.file_name,
                storage_path=src.storage_path,
                mime_type=src.mime_type,
                size_bytes=src.size_bytes,
                description=src.description,
                sort_order=src.sort_order,
            )
        )
    db.flush()


# --------------------------------------------------------------------------- #
# 30 天孤儿磁盘清理（Q115 / Q332 / §53.2 / Q371）—— 由 task 调用，逐项提交
# --------------------------------------------------------------------------- #
def _active_ref_count(db: Session, storage_path: str) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(ProcedureAttachment)
            .where(
                ProcedureAttachment.storage_path == storage_path,
                ProcedureAttachment.is_active.is_(True),
            )
        ).scalar_one()
    )


def orphan_storage_paths(db: Session, *, retention_days: int, now: datetime) -> list[str]:
    """无 active 引用、且存在软删 ≥ retention 天行的 storage_path 列表（清理候选）。"""
    threshold = now - timedelta(days=retention_days)
    aged = db.execute(
        select(ProcedureAttachment.storage_path)
        .where(
            ProcedureAttachment.is_active.is_(False),
            ProcedureAttachment.deleted_at.is_not(None),
            ProcedureAttachment.deleted_at <= threshold,
        )
        .distinct()
    ).scalars()
    grouped: dict[str, bool] = defaultdict(bool)
    for path in aged:
        grouped[path] = True
    return [p for p in grouped if _active_ref_count(db, p) == 0]


def delete_orphan_path(
    db: Session, storage_path: str, *, retention_days: int, now: datetime
) -> int:
    """重核无 active 引用 → 先删文件 → 硬删该 path 下软删 ≥ retention 天的行。返回删除行数。

    文件缺失视为成功；其他 OSError 抛出，由 task 记录并保留行下轮重试（§53.2）。
    """
    if _active_ref_count(db, storage_path) > 0:
        return 0
    get_storage_backend().delete(storage_path)  # 缺失幂等；其他 OSError 抛出由 task 记录并保留行下轮重试（§53.2）
    threshold = now - timedelta(days=retention_days)
    rows = db.execute(
        select(ProcedureAttachment).where(
            ProcedureAttachment.storage_path == storage_path,
            ProcedureAttachment.is_active.is_(False),
            ProcedureAttachment.deleted_at.is_not(None),
            ProcedureAttachment.deleted_at <= threshold,
        )
    ).scalars()
    deleted = 0
    for row in rows:
        db.delete(row)
        deleted += 1
    db.flush()
    return deleted
