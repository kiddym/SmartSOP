"""全局设置 service（api-specification §5.8 / data-model §3.8）。

settings 是单例：seed 时写入唯一一条 is_active=True 的记录。
service 只 flush，不 commit，事务由 router 提交。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.settings import ProcedureSettings
from app.schemas.settings import SettingsUpdate
from app.services import audit_service
from app.services.audit_service import AuditMeta
from app.services.optimistic_lock import bump


def get_singleton(db: Session) -> ProcedureSettings:
    """返回 active 单例。不存在时抛 404。"""
    obj = db.query(ProcedureSettings).filter(ProcedureSettings.is_active.is_(True)).first()
    if obj is None:
        raise not_found("SETTINGS_NOT_FOUND", "全局设置尚未初始化，请先运行 seed")
    return obj


def _to_dict(s: ProcedureSettings) -> dict[str, Any]:
    """将可审计字段序列化为字典（用于 diff）。"""
    return {
        "enable_approval_workflow": s.enable_approval_workflow,
        "max_version_number": s.max_version_number,
        "require_read_confirmation": s.require_read_confirmation,
        "default_risk_level": s.default_risk_level,
        "default_quality_level": s.default_quality_level,
    }


def update(
    db: Session,
    s: ProcedureSettings,
    payload: SettingsUpdate,
    meta: AuditMeta,
) -> ProcedureSettings:
    """应用更新，写审计日志，bump revision。只 flush，不 commit。"""
    old_dict = _to_dict(s)

    s.enable_approval_workflow = payload.enable_approval_workflow
    s.max_version_number = payload.max_version_number
    s.require_read_confirmation = payload.require_read_confirmation
    s.default_risk_level = payload.default_risk_level
    s.default_quality_level = payload.default_quality_level
    # enable_version_control 恒 true，auto_archive_days 0.1.0 不接线，两者忽略

    bump(s)

    new_dict = _to_dict(s)
    old_value, new_value = audit_service.compute_diff(old_dict, new_dict)

    # 0.1.0 临时方案：借用 procedure 审计表记录设置变更（target_id=settings.id, group=None）。
    # 未来如需按实体类型查询，应迁移到专属审计表。
    audit_service.log_procedure_action(
        db,
        target_id=s.id,
        procedure_group_id=None,
        action="settings_update",
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )

    db.flush()
    return s
