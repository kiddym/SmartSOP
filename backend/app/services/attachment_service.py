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
from sqlalchemy import ColumnElement, func, select
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


def _resolve_file_type(mime: str) -> str:
    """按已解析的 MIME 推断文件大类：image/* → 'IMAGE'，否则 'OTHER'（供全局文件库筛选）。"""
    return "IMAGE" if mime.lower().startswith("image/") else "OTHER"


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


def count_active(db: Session, entity_type: str, entity_id: str) -> int:
    """某宿主实体下 active 附件数（内部用，不做权限检查；调用方须已授权）。

    不使用 bypass_tenant_scope 是有意的——调用方已在请求租户上下文内，按当前
    company 计数正是所需，避免跨租户误计。与 _active_rows（为 procedure 等跨 scope
    宿主才 bypass）的差异是刻意设计：procedure 宿主在某些内部路径无租户上下文，
    故需 bypass；而工单步骤附件的调用方（update_step / execution_view）始终在
    租户上下文内，无需也不应 bypass。
    """
    return int(
        db.execute(
            select(func.count())
            .select_from(Attachment)
            .where(
                Attachment.entity_type == entity_type,
                Attachment.entity_id == entity_id,
                Attachment.is_active.is_(True),
            )
        ).scalar_one()
    )


def count_active_by_entity_ids(
    db: Session, entity_type: str, entity_ids: list[str]
) -> dict[str, int]:
    """批量：entity_id → active 附件数（仅返回有附件的 id）。

    不使用 bypass_tenant_scope 是有意的——调用方已在请求租户上下文内，按当前
    company 计数正是所需，避免跨租户误计。与 _active_rows（为 procedure 等跨 scope
    宿主才 bypass）的差异是刻意设计：execution_view 等批量统计调用方始终持有
    租户上下文，tenant 行级隔离已保证只命中本租户附件。
    """
    if not entity_ids:
        return {}
    rows = db.execute(
        select(Attachment.entity_id, func.count())
        .where(
            Attachment.entity_type == entity_type,
            Attachment.entity_id.in_(entity_ids),
            Attachment.is_active.is_(True),
        )
        .group_by(Attachment.entity_id)
    ).all()
    return {eid: int(n) for eid, n in rows}


def soft_delete_for_entities(db: Session, entity_type: str, entity_ids: list[str]) -> int:
    """将指定宿主 id 列表下的 active 附件批量软删（is_active=False + deleted_at）。

    返回实际软删条数。调用方负责 commit/flush 边界。
    典型场景：detach_procedure 硬删 WorkOrderStepResult 行前，先软删其附件，
    避免孤儿附件残留到定时清理才消失。
    """
    if not entity_ids:
        return 0
    now = utcnow()
    with tenant.bypass_tenant_scope():
        rows = list(
            db.execute(
                select(Attachment).where(
                    Attachment.entity_type == entity_type,
                    Attachment.entity_id.in_(entity_ids),
                    Attachment.is_active.is_(True),
                )
            ).scalars()
        )
    for att in rows:
        att.is_active = False
        att.deleted_at = now
    db.flush()
    return len(rows)


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
            select(Attachment).where(Attachment.id == attachment_id, Attachment.is_active.is_(True))
        ).scalar_one_or_none()
    if att is None:
        raise not_found("NOT_FOUND", "附件不存在")
    return att


def list_for(db: Session, user: User | None, entity_type: str, entity_id: str) -> list[Attachment]:
    entities.resolve_and_authorize(db, user, entity_type, entity_id, "read")
    return _active_rows(db, entity_type, entity_id)


def list_library(
    db: Session,
    *,
    entity_type: str | None = None,
    file_type: str | None = None,
    include_hidden: bool = False,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Attachment], int]:
    """全局文件库：当前租户下跨实体列出 active 附件（不走 bypass，依赖 tenant 行级隔离）。

    权限口径：任意认证用户可读，仅返回当前 company 的附件（tenant 自动作用域）。
    procedure 附件 company_id 可能为 NULL（SOP 表 phase-0 容忍），租户作用域下不会
    泄漏给其他公司，但也不会归属任何公司 → 全局文件库不含此类无主 procedure 附件。
    返回 (当前页行, 命中总数)。
    """
    conds: list[ColumnElement[bool]] = [Attachment.is_active.is_(True)]
    if entity_type:
        conds.append(Attachment.entity_type == entity_type)
    if file_type:
        conds.append(Attachment.file_type == file_type)
    if not include_hidden:
        conds.append(Attachment.hidden.is_(False))
    if q:
        conds.append(Attachment.file_name.ilike(f"%{q}%"))

    total = int(db.execute(select(func.count()).select_from(Attachment).where(*conds)).scalar_one())
    rows = list(
        db.execute(
            select(Attachment)
            .where(*conds)
            .order_by(Attachment.created_at.desc(), Attachment.id)
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    return rows, total


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

    mime = _resolve_mime(name, content_type)
    att = Attachment(
        # 显式落宿主 company_id：procedure 宿主解析走 bypass，且内部写路径可能无
        # tenant 上下文（自动盖值不生效）。附件归属随宿主，故直接取宿主的 company_id。
        company_id=host.company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        file_name=name,
        storage_path=rel,
        mime_type=mime,
        file_type=_resolve_file_type(mime),
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
    hidden: bool | None = None,
    meta: RequestMeta,
) -> Attachment:
    """改元数据（description / sort_order / hidden）+ 钩子。"""
    att = get_or_404(db, attachment_id)
    host = entities.resolve_and_authorize(db, user, att.entity_type, att.entity_id, "write")

    before = {
        "description": att.description,
        "sort_order": att.sort_order,
        "hidden": att.hidden,
    }
    if description is not None:
        att.description = description.strip()
    if sort_order is not None:
        att.sort_order = sort_order
    if hidden is not None:
        att.hidden = hidden
    db.flush()
    after = {
        "description": att.description,
        "sort_order": att.sort_order,
        "hidden": att.hidden,
    }
    if att.entity_type == "procedure":
        old_value, new_value = audit_service.compute_diff(before, after)
        if new_value:
            hooks.procedure_audit_update(
                db, host, att, meta=meta, old_value=old_value, new_value=new_value
            )
    return att


def delete_for(db: Session, user: User | None, attachment_id: str, *, meta: RequestMeta) -> None:
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
                # 附件归属随宿主：复制版本时显式沿用源附件（同宿主链）的 company_id。
                company_id=src.company_id,
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
def soft_delete_orphaned_by_host(db: Session) -> int:
    """扫各 entity_type 的 active 附件，宿主不存在 → 软删附件。返回软删条数。bypass 跨租户。"""
    soft_deleted = 0
    with tenant.bypass_tenant_scope():
        rows = list(db.execute(select(Attachment).where(Attachment.is_active.is_(True))).scalars())
        existing: dict[tuple[str, str], bool] = {}
        for att in rows:
            spec = entities.ENTITY_REGISTRY.get(att.entity_type)
            if spec is None:
                continue
            key = (att.entity_type, att.entity_id)
            if key not in existing:
                host = db.execute(
                    select(spec.model.id).where(
                        spec.model.id == att.entity_id,
                        spec.model.is_active.is_(True),
                    )
                ).scalar_one_or_none()
                existing[key] = host is not None
            if not existing[key]:
                att.is_active = False
                att.deleted_at = utcnow()
                soft_deleted += 1
        db.flush()
    return soft_deleted


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
