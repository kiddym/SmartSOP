"""原始 Word 源文件存取（P1：导入可追溯）。

导入时把临时区 source.docx 永久落库（按 procedure_group 一份）；编辑器预览栏按
procedure_id 取回渲染；删除纯草稿时连带清理。与图片中心的 asset_service 平行、解耦。
不在顶层 import procedure_service（避免循环）：直接查 Procedure。
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.config import settings
from app.errors import not_found
from app.models.procedure import Procedure
from app.models.source_docx import ProcedureSourceDocx
from app.parser.utils.opc import is_docx_bytes
from app.services import upload_service
from app.storage_backends import get_storage_backend

_FILENAME_MAX = 255  # 与 ProcedureSourceDocx.filename String(255) 对齐

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def store_from_token(
    db: Session, *, procedure_group_id: str, upload_token: str | None
) -> ProcedureSourceDocx | None:
    """把临时 docx 永久落库；token 缺失/过期/丢失 → None（降级，不阻断导入）。"""
    if not upload_token:
        return None
    read = upload_service.try_read_source(upload_token)
    if read is None:
        return None
    data, filename = read
    # 永久化边界再校验（深度防御）：临时文件可能在上传后被改。超限/非法 docx → 降级跳过存储、
    # 不阻断导入（与 token 缺失一致）；文件名截断到列宽，避免 MySQL 上 INSERT DataError。
    if len(data) > settings.upload_max_size_mb * 1024 * 1024 or not is_docx_bytes(data):
        return None
    filename = filename[:_FILENAME_MAX]
    path = storage.source_docx_path(procedure_group_id)
    # 先 flush 行、后落盘：DB 完整性（unique / 列长）先于写文件校验，使任何失败最多残留
    # “有行无文件”（get_for_procedure 优雅降级、delete_for_group 可清），而非“有文件无行”
    # 的静默磁盘泄漏（source_docx/ 无 GC）。
    row = ProcedureSourceDocx(
        procedure_group_id=procedure_group_id,
        filename=filename,
        storage_path=str(path.relative_to(storage.storage_root())),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )
    db.add(row)
    db.flush()
    backend = get_storage_backend()
    try:
        backend.write(row.storage_path, data)
    except Exception:
        backend.delete(row.storage_path)  # 清半截文件；行随事务回滚消失
        raise
    return row


def get_for_procedure(db: Session, procedure_id: str) -> tuple[Path, str, str]:
    """按 procedure_id → group → 返回 (落盘路径, mime, 原始文件名)，供流式下载。无 → 404。"""
    proc = db.execute(
        select(Procedure).where(Procedure.id == procedure_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    row = db.execute(
        select(ProcedureSourceDocx).where(
            ProcedureSourceDocx.procedure_group_id == proc.procedure_group_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found("SOURCE_DOCX_NOT_FOUND", "该程序无原始 Word 源文件")
    # 读路径维持本地 FS：调用方（routers/procedures.serve_source_docx）以 FileResponse
    # 流式下载，强依赖真实磁盘路径。S3 后端下源 docx 下载需先 download 到临时文件，属未来 ops 工作。
    path = storage.storage_root() / row.storage_path
    if not path.exists():
        raise not_found("SOURCE_DOCX_NOT_FOUND", "原始 Word 源文件已丢失")
    return path, _DOCX_MIME, row.filename


def exists_for_procedure(db: Session, procedure_id: str) -> bool:
    """该程序所属 group 是否存有原始 Word 源文件（供前端决定是否拉取预览，避免无谓 404）。"""
    proc = db.execute(
        select(Procedure).where(Procedure.id == procedure_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        return False
    return (
        db.execute(
            select(ProcedureSourceDocx.id).where(
                ProcedureSourceDocx.procedure_group_id == proc.procedure_group_id
            )
        ).first()
        is not None
    )


def delete_for_group(db: Session, procedure_group_id: str) -> None:
    """删除某 group 的源 docx（行 + 落盘文件）。无则静默。"""
    row = db.execute(
        select(ProcedureSourceDocx).where(
            ProcedureSourceDocx.procedure_group_id == procedure_group_id
        )
    ).scalar_one_or_none()
    if row is None:
        return
    get_storage_backend().delete(row.storage_path)
    db.delete(row)
    db.flush()


def orphan_group_ids(db: Session) -> list[str]:
    """source_docx/ 下无对应 DB 行的 group 目录名（落盘孤儿：历史缺陷遗留 / 删组后空目录）。"""
    root = storage.source_docx_root()
    if not root.exists():
        return []
    known = {gid for (gid,) in db.execute(select(ProcedureSourceDocx.procedure_group_id)).all()}
    return sorted(d.name for d in root.iterdir() if d.is_dir() and d.name not in known)


def delete_group_dir(procedure_group_id: str) -> bool:
    """物理删除某 group 的落盘目录（孤儿清理用，不碰 DB）。返回是否实际删除。"""
    # 目录枚举型孤儿清理仅本地后端有效：S3 无目录概念，源 docx 孤儿清理在 S3 下属未来 ops 工具。
    d = storage.source_docx_root() / procedure_group_id
    if not d.exists():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return True
