"""procedure 实体的附件写钩子（草稿态校验 + 审计），隔离 service↔procedure 耦合。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.attachment import Attachment
from app.models.procedure import Procedure
from app.services import audit_service


def procedure_write_guard(host: Any) -> None:
    """仅当前草稿可写附件：废止→PROCEDURE_DEPRECATED；非当前草稿→PROCEDURE_READONLY。"""
    assert isinstance(host, Procedure)
    proc = host
    if proc.deprecated_at is not None:
        raise bad_request("PROCEDURE_DEPRECATED", "程序已被废止，请先恢复后再操作")
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑附件")


def procedure_audit_upload(
    db: Session,
    host: Any,
    att: Attachment,
    *,
    meta: audit_service.AuditMeta,
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=att.id,
        procedure_group_id=host.procedure_group_id,
        action="upload",
        meta=meta,
        new_value={"file_name": att.file_name, "size_bytes": att.size_bytes},
    )


def procedure_audit_update(
    db: Session,
    host: Any,
    att: Attachment,
    *,
    meta: audit_service.AuditMeta,
    old_value: dict[str, Any],
    new_value: dict[str, Any],
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=att.id,
        procedure_group_id=host.procedure_group_id,
        action="update",
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )


def procedure_audit_delete(
    db: Session,
    host: Any,
    att: Attachment,
    *,
    meta: audit_service.AuditMeta,
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=att.id,
        procedure_group_id=host.procedure_group_id,
        action="delete",
        meta=meta,
        old_value={"file_name": att.file_name},
    )
