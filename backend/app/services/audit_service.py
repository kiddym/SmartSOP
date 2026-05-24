"""审计日志写入封装（data-model §3.9 / Q122-Q128 / Q324）。

追加式写日志：folder / procedure 两表。字段级 diff（Q123）；rollback/deprecate/
restore/delete 必填 reason（Q128，由调用方保证）。IP/UA 来自请求元信息（真实
客户端 IP 解析见 deps.get_request_meta + utils.net，Q324）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import FolderAuditLog, ProcedureAuditLog

logger = logging.getLogger(__name__)


class AuditMeta(Protocol):
    """审计所需的请求元信息（结构化匹配 deps.RequestMeta，避免层间耦合）。

    用只读 property 声明，使 frozen dataclass（RequestMeta）也满足该协议。
    """

    @property
    def ip_address(self) -> str: ...

    @property
    def user_agent(self) -> str: ...


def compute_diff(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """计算字段级 diff，仅保留发生变化的键（Q123）。

    取 before/after 键的并集，使「被移除的键」也能被记录到 diff。
    """
    old_value: dict[str, Any] = {}
    new_value: dict[str, Any] = {}
    for key in before.keys() | after.keys():
        if before.get(key) != after.get(key):
            old_value[key] = before.get(key)
            new_value[key] = after.get(key)
    return old_value, new_value


def log_folder_action(
    db: Session,
    *,
    target_id: str,
    action: str,
    meta: AuditMeta,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str = "",
) -> FolderAuditLog:
    """写一条文件夹审计日志（不 commit，由调用方提交）。"""
    entry = FolderAuditLog(
        target_id=target_id,
        action=action,
        old_value=old_value or {},
        new_value=new_value or {},
        reason=reason,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
    )
    db.add(entry)
    logger.info("folder audit action=%s target=%s", action, target_id)
    return entry


def log_procedure_action(
    db: Session,
    *,
    target_id: str,
    procedure_group_id: str | None,
    action: str,
    meta: AuditMeta,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str = "",
) -> ProcedureAuditLog:
    """写一条程序审计日志（冗存 procedure_group_id，Q127）。不 commit。"""
    entry = ProcedureAuditLog(
        target_id=target_id,
        procedure_group_id=procedure_group_id,
        action=action,
        old_value=old_value or {},
        new_value=new_value or {},
        reason=reason,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
    )
    db.add(entry)
    logger.info(
        "procedure audit action=%s target=%s group=%s",
        action,
        target_id,
        procedure_group_id,
    )
    return entry


# ---------------------------------------------------------------------------
# 查询函数（只读，api-specification §5.9 / Q126-Q127）
# ---------------------------------------------------------------------------


def _apply_common_filters(
    q: Any,
    model: Any,
    *,
    target_id: str | None,
    action: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    ip_address: str | None,
) -> Any:
    """将公共过滤条件应用到查询，返回过滤后的查询对象。"""
    if target_id:
        q = q.where(model.target_id == target_id)
    if action:
        actions = [a.strip() for a in action.split(",") if a.strip()]
        if actions:
            q = q.where(model.action.in_(actions))
    if date_from:
        q = q.where(model.created_at >= date_from)
    if date_to:
        q = q.where(model.created_at <= date_to)
    if ip_address:
        q = q.where(model.ip_address == ip_address)
    return q


def query_folder_audit(
    db: Session,
    *,
    target_id: str | None,
    action: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    ip_address: str | None,
    page: int,
    page_size: int,
) -> tuple[int, list[FolderAuditLog]]:
    """分页查询文件夹审计日志，返回 (total, items)。"""
    q = select(FolderAuditLog)
    q = _apply_common_filters(
        q,
        FolderAuditLog,
        target_id=target_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
    )
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    items = list(
        db.execute(
            q.order_by(FolderAuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    return int(total), items


def query_folder_audit_all(
    db: Session,
    *,
    target_id: str | None,
    action: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    ip_address: str | None,
) -> list[FolderAuditLog]:
    """全量查询文件夹审计日志（CSV 导出用），按 created_at 升序。"""
    q = select(FolderAuditLog)
    q = _apply_common_filters(
        q,
        FolderAuditLog,
        target_id=target_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
    )
    return list(db.execute(q.order_by(FolderAuditLog.created_at.asc())).scalars())


def query_procedure_audit(
    db: Session,
    *,
    target_id: str | None,
    procedure_group_id: str | None,
    action: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    ip_address: str | None,
    page: int,
    page_size: int,
) -> tuple[int, list[ProcedureAuditLog]]:
    """分页查询程序审计日志，返回 (total, items)。"""
    q = select(ProcedureAuditLog)
    q = _apply_common_filters(
        q,
        ProcedureAuditLog,
        target_id=target_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
    )
    if procedure_group_id:
        q = q.where(ProcedureAuditLog.procedure_group_id == procedure_group_id)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    items = list(
        db.execute(
            q.order_by(ProcedureAuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    return int(total), items


def query_procedure_audit_all(
    db: Session,
    *,
    target_id: str | None,
    procedure_group_id: str | None,
    action: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    ip_address: str | None,
) -> list[ProcedureAuditLog]:
    """全量查询程序审计日志（CSV 导出用），按 created_at 升序。"""
    q = select(ProcedureAuditLog)
    q = _apply_common_filters(
        q,
        ProcedureAuditLog,
        target_id=target_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
    )
    if procedure_group_id:
        q = q.where(ProcedureAuditLog.procedure_group_id == procedure_group_id)
    return list(db.execute(q.order_by(ProcedureAuditLog.created_at.asc())).scalars())
