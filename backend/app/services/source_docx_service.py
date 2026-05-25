"""原始 Word 源文件存取（P1：导入可追溯）。

导入时把临时区 source.docx 永久落库（按 procedure_group 一份）；编辑器预览栏按
procedure_id 取回渲染；删除纯草稿时连带清理。与图片中心的 asset_service 平行、解耦。
不在顶层 import procedure_service（避免循环）：直接查 Procedure。
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.errors import not_found
from app.models.procedure import Procedure
from app.models.source_docx import ProcedureSourceDocx
from app.services import upload_service

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
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(data)
    except OSError:
        path.unlink(missing_ok=True)  # 清半截文件；行随事务回滚消失
        raise
    return row


def get_for_procedure(db: Session, procedure_id: str) -> tuple[bytes, str, str]:
    """按 procedure_id → group → 返回 (字节, mime, 原始文件名)。无 → 404。"""
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
    path = storage.storage_root() / row.storage_path
    if not path.exists():
        raise not_found("SOURCE_DOCX_NOT_FOUND", "原始 Word 源文件已丢失")
    return path.read_bytes(), _DOCX_MIME, row.filename


def delete_for_group(db: Session, procedure_group_id: str) -> None:
    """删除某 group 的源 docx（行 + 落盘文件）。无则静默。"""
    row = db.execute(
        select(ProcedureSourceDocx).where(
            ProcedureSourceDocx.procedure_group_id == procedure_group_id
        )
    ).scalar_one_or_none()
    if row is None:
        return
    (storage.storage_root() / row.storage_path).unlink(missing_ok=True)
    db.delete(row)
    db.flush()
