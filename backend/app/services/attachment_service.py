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

from app import storage, tenant
from app.deps import RequestMeta
from app.errors import app_error, bad_request, not_found
from app.models.attachment import Attachment
from app.models.base import new_uuid, utcnow
from app.models.user import User
from app.services import attachment_entities as entities
from app.services import attachment_hooks as hooks
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
def _resolve_mime(file_name: str, content_type: str | None) -> str:
    """优先用上传声明的 content_type，缺失/通用则按扩展名猜测，最终回退 octet-stream。"""
    if content_type and content_type != _DEFAULT_MIME:
        return content_type
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed or _DEFAULT_MIME


def _active_rows(db: Session, entity_type: str, entity_id: str) -> list[Attachment]:
    with tenant.bypass_tenant_scope():
        return list(
            db.execute(
                select(Attachment)
                .where(
                    Attachment.entity_type == entity_type,
                    Attachment.entity_id == entity_id,
                    Attachment.is_active.is_(True),
                )
                .order_by(Attachment.sort_order, Attachment.created_at)
            ).scalars()
        )


def _bytes_or_404(att: Attachment) -> bytes:
    try:
        return get_storage_backend().read(att.storage_path)
    except FileNotFoundError:
        raise not_found("NOT_FOUND", "附件文件已丢失") from None


# --------------------------------------------------------------------------- #
# 读取（泛型）
# --------------------------------------------------------------------------- #
def get_or_404(db: Session, attachment_id: str) -> Attachment:
    with tenant.bypass_tenant_scope():
        att = db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id, Attachment.is_active.is_(True)
            )
        ).scalar_one_or_none()
    if att is None:
        raise not_found("NOT_FOUND", "附件不存在")
    return att


def list_for(
    db: Session, user: User | None, entity_type: str, entity_id: str
) -> list[Attachment]:
    entities.resolve_and_authorize(db, user, entity_type, entity_id, "read")
    return _active_rows(db, entity_type, entity_id)


def download_for(db: Session, user: User | None, attachment_id: str) -> tuple[bytes, str, str]:
    att = get_or_404(db, attachment_id)
    entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "read")
    return _bytes_or_404(att), att.mime_type, att.file_name


def preview_for(db: Session, user: User | None, attachment_id: str) -> tuple[bytes, str]:
    att = get_or_404(db, attachment_id)
    entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "read")
    if att.mime_type not in PREVIEW_WHITELIST:
        raise app_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "ATTACHMENT_NOT_PREVIEWABLE",
            "该类型不支持在线预览",
        )
    return _bytes_or_404(att), att.mime_type


# --------------------------------------------------------------------------- #
# 写入（泛型）
# --------------------------------------------------------------------------- #
def upload_for(
    db: Session,
    user: User | None,
    entity_type: str,
    entity_id: str,
    data: bytes,
    file_name: str,
    *,
    content_type: str | None,
    description: str,
    meta: RequestMeta,
) -> Attachment:
    """上传附件（resolve+authorize 含 write_guard）+ 上限校验 + 落盘 + 钩子。"""
    host = entities.resolve_and_authorize(db, user, entity_type, entity_id, "write")

    size = len(data)
    if size > MAX_FILE_BYTES:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "单文件超过 50MB 上限", field="file")
    existing = _active_rows(db, entity_type, entity_id)
    if len(existing) + 1 > MAX_COUNT:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "附件数量超过 30 个上限", field="file")
    if sum(a.size_bytes for a in existing) + size > MAX_TOTAL_BYTES:
        raise bad_request("ATTACHMENT_LIMIT_EXCEEDED", "附件总大小超过 200MB 上限", field="file")

    name = file_name.strip() or "未命名"
    uid = new_uuid()
    path = storage.attachment_path(uid, Path(name).suffix)
    rel = path.relative_to(storage.storage_root()).as_posix()
    get_storage_backend().write(rel, data)

    att = Attachment(
        entity_type=entity_type,
        entity_id=entity_id,
        file_name=name,
        storage_path=rel,
        mime_type=_resolve_mime(name, content_type),
        size_bytes=size,
        description=description.strip(),
        sort_order=len(existing),
    )
    db.add(att)
    db.flush()
    if entity_type == "procedure":
        hooks.procedure_audit_upload(db, host, att, meta=meta)
    return att


def update_for(
    db: Session,
    user: User | None,
    attachment_id: str,
    *,
    description: str | None,
    sort_order: int | None,
    meta: RequestMeta,
) -> Attachment:
    """改元数据（仅 description / sort_order）+ 钩子。"""
    att = get_or_404(db, attachment_id)
    host = entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "write")

    before = {"description": att.description, "sort_order": att.sort_order}
    if description is not None:
        att.description = description.strip()
    if sort_order is not None:
        att.sort_order = sort_order
    db.flush()
    after = {"description": att.description, "sort_order": att.sort_order}
    if att.entity_type == "procedure":
        old_value, new_value = audit_service.compute_diff(before, after)
        if new_value:
            hooks.procedure_audit_update(
                db, host, att, meta=meta, old_value=old_value, new_value=new_value
            )
    return att


def delete_for(
    db: Session, user: User | None, attachment_id: str, *, meta: RequestMeta
) -> None:
    """软删 + 钩子。"""
    att = get_or_404(db, attachment_id)
    host = entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "write")

    att.is_active = False
    att.deleted_at = utcnow()
    db.flush()
    if att.entity_type == "procedure":
        hooks.procedure_audit_delete(db, host, att, meta=meta)


# --------------------------------------------------------------------------- #
# procedure_service 内嵌查询（get_detail 用）
# --------------------------------------------------------------------------- #
def rows_for(db: Session, procedure_id: str) -> list[Attachment]:
    """get_detail 内嵌用：直接查 active 附件行（proc 已由调用方保证存在）。"""
    return _active_rows(db, "procedure", procedure_id)


# --------------------------------------------------------------------------- #
# 跨版本元数据复制（Q113 / Q117 / Q371）—— 由 version_flow_service 调用
# --------------------------------------------------------------------------- #
def copy_for_version(db: Session, src_procedure_id: str, dst_procedure_id: str) -> None:
    """复制 src 版本的 active 附件元数据到 dst（新 id、复用 storage_path，物理文件不复制）。"""
    for src in _active_rows(db, "procedure", src_procedure_id):
        db.add(
            Attachment(
                entity_type="procedure",
                entity_id=dst_procedure_id,
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
            .select_from(Attachment)
            .where(
                Attachment.storage_path == storage_path,
                Attachment.is_active.is_(True),
            )
        ).scalar_one()
    )


def orphan_storage_paths(db: Session, *, retention_days: int, now: datetime) -> list[str]:
    """无 active 引用、且存在软删 ≥ retention 天行的 storage_path 列表（清理候选）。"""
    threshold = now - timedelta(days=retention_days)
    aged = db.execute(
        select(Attachment.storage_path)
        .where(
            Attachment.is_active.is_(False),
            Attachment.deleted_at.is_not(None),
            Attachment.deleted_at <= threshold,
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
    get_storage_backend().delete(
        storage_path
    )  # 缺失幂等；其他 OSError 抛出由 task 记录并保留行下轮重试（§53.2）
    threshold = now - timedelta(days=retention_days)
    rows = db.execute(
        select(Attachment).where(
            Attachment.storage_path == storage_path,
            Attachment.is_active.is_(False),
            Attachment.deleted_at.is_not(None),
            Attachment.deleted_at <= threshold,
        )
    ).scalars()
    deleted = 0
    for row in rows:
        db.delete(row)
        deleted += 1
    db.flush()
    return deleted
