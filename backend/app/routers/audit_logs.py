"""审计日志查询路由（只读，api-specification §5.9 / Q126-Q127）。

提供文件夹与程序两类审计日志的分页查询及 CSV 全量导出。
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.audit_log import (
    AuditLogItem,
    AuditLogPage,
    ProcedureAuditLogItem,
    ProcedureAuditLogPage,
)
from app.services import audit_service

router = APIRouter(prefix="/api/v1", tags=["audit-logs"])

_FOLDER_CSV_HEADERS = [
    "id",
    "target_id",
    "action",
    "old_value",
    "new_value",
    "reason",
    "ip_address",
    "user_agent",
    "created_at",
]

_PROCEDURE_CSV_HEADERS = [
    "id",
    "target_id",
    "action",
    "old_value",
    "new_value",
    "reason",
    "ip_address",
    "user_agent",
    "created_at",
    "procedure_group_id",
]


def _row_to_folder_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "target_id": row.target_id,
        "action": row.action,
        "old_value": json.dumps(row.old_value or {}, ensure_ascii=False),
        "new_value": json.dumps(row.new_value or {}, ensure_ascii=False),
        "reason": row.reason,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _row_to_procedure_dict(row: Any) -> dict[str, Any]:
    d = _row_to_folder_dict(row)
    d["procedure_group_id"] = row.procedure_group_id
    return d


def _build_csv_response(
    headers: list[str],
    rows: Sequence[Any],
    row_fn: Callable[[Any], dict[str, Any]],
    filename: str,
) -> StreamingResponse:
    buf = io.BytesIO()
    buf.write(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
    text_buf = io.StringIO()
    writer = csv.DictWriter(text_buf, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow(row_fn(row))
    buf.write(text_buf.getvalue().encode("utf-8"))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/audit-logs/folders", response_model=None)
def list_folder_audit(
    target_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    ip_address: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    export: str | None = None,
    db: Session = Depends(get_db),
) -> AuditLogPage | StreamingResponse:
    """查询文件夹审计日志（分页或 CSV 导出）。"""
    if export == "csv":
        rows = audit_service.query_folder_audit_all(
            db,
            target_id=target_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            ip_address=ip_address,
        )
        return _build_csv_response(
            _FOLDER_CSV_HEADERS,
            rows,
            _row_to_folder_dict,
            "audit_folders.csv",
        )

    total, items = audit_service.query_folder_audit(
        db,
        target_id=target_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
        page=page,
        page_size=page_size,
    )
    return AuditLogPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[AuditLogItem.model_validate(i) for i in items],
    )


@router.get("/audit-logs/procedures", response_model=None)
def list_procedure_audit(
    target_id: str | None = None,
    procedure_group_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    ip_address: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    export: str | None = None,
    db: Session = Depends(get_db),
) -> ProcedureAuditLogPage | StreamingResponse:
    """查询程序审计日志（分页或 CSV 导出）。"""
    if export == "csv":
        rows = audit_service.query_procedure_audit_all(
            db,
            target_id=target_id,
            procedure_group_id=procedure_group_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            ip_address=ip_address,
        )
        return _build_csv_response(
            _PROCEDURE_CSV_HEADERS,
            rows,
            _row_to_procedure_dict,
            "audit_procedures.csv",
        )

    total, items = audit_service.query_procedure_audit(
        db,
        target_id=target_id,
        procedure_group_id=procedure_group_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
        page=page,
        page_size=page_size,
    )
    return ProcedureAuditLogPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[ProcedureAuditLogItem.model_validate(i) for i in items],
    )
