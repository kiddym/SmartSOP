"""PM 服务：CRUD、customId、enable/disable、生单+锥摆推进、活动时间线。

调度任务与手动端点共用 generate_once。工单服务在函数内 import 避免循环依赖。
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.work_order import WorkOrder

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.base import utcnow
from app.models.pm_activity import PMActivity
from app.models.pm_frequency import PMFrequencyUnit
from app.models.preventive_maintenance import (
    PMAssignee,
    PMTeam,
    PreventiveMaintenance,
)
from app.schemas.pm import PMCreate, PMUpdate
from app.services import sequence_service


def _add_interval(d: date, unit: PMFrequencyUnit, value: int) -> date:
    """在 d 上加 value 个 unit。MONTH 钳制到目标月最后一天。"""
    if unit == PMFrequencyUnit.DAY:
        from datetime import timedelta

        return d + timedelta(days=value)
    if unit == PMFrequencyUnit.WEEK:
        from datetime import timedelta

        return d + timedelta(days=value * 7)
    # MONTH
    total = (d.year * 12 + (d.month - 1)) + value
    year, month = divmod(total, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _advance_due(next_due: date, unit: PMFrequencyUnit, value: int, *, today: date) -> date:
    """锥摆推进：从 next_due 连加周期直到 > today（一期一单、不补单）。
    next_due 已在未来时为 no-op。value>=1 保证严格递增、不死循环。"""
    nd = next_due
    while nd <= today:
        nd = _add_interval(nd, unit, value)
    return nd


def _log(
    db: Session,
    pm_id: str,
    company_id: str,
    activity_type: str,
    actor_user_id: str | None = None,
    comment: str = "",
) -> None:
    db.add(
        PMActivity(
            pm_id=pm_id,
            company_id=company_id,
            activity_type=activity_type,
            actor_user_id=actor_user_id,
            comment=comment,
        )
    )


def assignee_ids(db: Session, pm_id: str) -> list[str]:
    return list(
        db.execute(
            select(PMAssignee.user_id).where(PMAssignee.pm_id == pm_id).order_by(PMAssignee.user_id)
        )
        .scalars()
        .all()
    )


def team_ids(db: Session, pm_id: str) -> list[str]:
    return list(
        db.execute(select(PMTeam.team_id).where(PMTeam.pm_id == pm_id).order_by(PMTeam.team_id))
        .scalars()
        .all()
    )


def _set_relations(
    db: Session,
    pm: PreventiveMaintenance,
    company_id: str,
    user_ids: list[str],
    team_id_list: list[str],
) -> None:
    for uid in dict.fromkeys(user_ids):
        db.add(PMAssignee(pm_id=pm.id, user_id=uid, company_id=company_id))
    for tid in dict.fromkeys(team_id_list):
        db.add(PMTeam(pm_id=pm.id, team_id=tid, company_id=company_id))


def create_pm(
    db: Session, payload: PMCreate, company_id: str, actor_user_id: str | None
) -> PreventiveMaintenance:
    seq = sequence_service.next_value(db, "preventive_maintenance", company_id)
    pm = PreventiveMaintenance(
        custom_id=sequence_service.format_custom_id("PM", seq),
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        asset_id=payload.asset_id,
        location_id=payload.location_id,
        primary_user_id=payload.primary_user_id,
        procedure_id=payload.procedure_id,
        start_date=payload.start_date,
        frequency_unit=payload.frequency_unit,
        frequency_value=payload.frequency_value,
        due_date_delay=payload.due_date_delay,
        ends_on=payload.ends_on,
        next_due_date=payload.start_date,
        company_id=company_id,
    )
    db.add(pm)
    db.flush()
    _set_relations(db, pm, company_id, payload.assignee_ids, payload.team_ids)
    _log(db, pm.id, company_id, "CREATED", actor_user_id=actor_user_id)
    db.commit()
    db.refresh(pm)
    return pm


def list_pms(
    db: Session,
    *,
    is_enabled: bool | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
) -> list[PreventiveMaintenance]:
    stmt = select(PreventiveMaintenance).where(PreventiveMaintenance.is_active.is_(True))
    if is_enabled is not None:
        stmt = stmt.where(PreventiveMaintenance.is_enabled.is_(is_enabled))
    if asset_id is not None:
        stmt = stmt.where(PreventiveMaintenance.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(PreventiveMaintenance.location_id == location_id)
    return list(db.execute(stmt.order_by(PreventiveMaintenance.custom_id)).scalars().all())


def get_pm(db: Session, pm_id: str) -> PreventiveMaintenance | None:
    pm = db.get(PreventiveMaintenance, pm_id)
    if pm is None or not pm.is_active:
        return None
    return pm


def update_pm(
    db: Session,
    pm: PreventiveMaintenance,
    payload: PMUpdate,
    company_id: str,
    actor_user_id: str | None,
) -> PreventiveMaintenance:
    data = payload.model_dump(exclude_unset=True)
    new_assignees = data.pop("assignee_ids", None)
    new_teams = data.pop("team_ids", None)
    for k, v in data.items():
        setattr(pm, k, v)
    if "start_date" in data:  # 改 start_date -> 重置 next_due
        pm.next_due_date = pm.start_date
    if pm.frequency_value < 1:
        raise bad_request("PM_INVALID_FREQUENCY", "频率间隔需≥1")
    if new_assignees is not None:
        db.execute(delete(PMAssignee).where(PMAssignee.pm_id == pm.id))
        for uid in dict.fromkeys(new_assignees):
            db.add(PMAssignee(pm_id=pm.id, user_id=uid, company_id=company_id))
    if new_teams is not None:
        db.execute(delete(PMTeam).where(PMTeam.pm_id == pm.id))
        for tid in dict.fromkeys(new_teams):
            db.add(PMTeam(pm_id=pm.id, team_id=tid, company_id=company_id))
    _log(db, pm.id, company_id, "UPDATED", actor_user_id=actor_user_id)
    db.commit()
    db.refresh(pm)
    return pm


def delete_pm(db: Session, pm: PreventiveMaintenance) -> None:
    pm.is_active = False
    pm.deleted_at = utcnow()
    db.commit()


def enable_pm(
    db: Session, pm: PreventiveMaintenance, company_id: str, actor_user_id: str | None
) -> PreventiveMaintenance:
    pm.is_enabled = True
    _log(db, pm.id, company_id, "ENABLED", actor_user_id=actor_user_id)
    db.commit()
    db.refresh(pm)
    return pm


def disable_pm(
    db: Session, pm: PreventiveMaintenance, company_id: str, actor_user_id: str | None
) -> PreventiveMaintenance:
    pm.is_enabled = False
    _log(db, pm.id, company_id, "DISABLED", actor_user_id=actor_user_id)
    db.commit()
    db.refresh(pm)
    return pm


def add_comment(
    db: Session, pm: PreventiveMaintenance, comment: str, company_id: str, actor_user_id: str | None
) -> PMActivity:
    act = PMActivity(
        pm_id=pm.id,
        company_id=company_id,
        activity_type="COMMENT",
        actor_user_id=actor_user_id,
        comment=comment,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def list_activities(db: Session, pm_id: str) -> list[PMActivity]:
    return list(
        db.execute(
            select(PMActivity)
            .where(PMActivity.pm_id == pm_id)
            .order_by(PMActivity.created_at, PMActivity.id)
        )
        .scalars()
        .all()
    )


def due_candidates(db: Session, *, today: date) -> list[str]:
    """跨租户取到期 PM id（调用方需已 bypass_tenant_scope）。"""
    stmt = (
        select(PreventiveMaintenance.id)
        .where(
            PreventiveMaintenance.is_active.is_(True),
            PreventiveMaintenance.is_enabled.is_(True),
            PreventiveMaintenance.next_due_date <= today,
        )
        .order_by(PreventiveMaintenance.custom_id)
    )
    return list(db.execute(stmt).scalars().all())


AUTO_DISABLE_THRESHOLD = 5
"""连续 N 张自动生成工单无人响应即自动停用 PM（防僵尸刷单）。"""


def _evaluate_auto_disable(db: Session, pm: PreventiveMaintenance, *, now: datetime) -> bool:
    """评估上一张自动生成工单的响应情况，更新连续无响应计数。

    近似信号（WorkOrder 无 pm_id 反查）：仅看 last_work_order_id 这张。
    若其仍 OPEN 且 first_responded_at 为空 -> 计数+1；否则归零。
    达阈值则停用 PM 并返回 True（调用方跳过本次生成）。"""
    from app.models.work_order import WorkOrder
    from app.models.work_order_status import WorkOrderStatus

    if pm.last_work_order_id is not None:
        prev = db.get(WorkOrder, pm.last_work_order_id)
        unresponded = (
            prev is not None
            and prev.is_active
            and prev.first_responded_at is None
            and prev.status == WorkOrderStatus.OPEN
        )
        pm.consecutive_unresponded = (pm.consecutive_unresponded + 1) if unresponded else 0
    if pm.consecutive_unresponded >= AUTO_DISABLE_THRESHOLD:
        pm.is_enabled = False
        pm.consecutive_unresponded = 0
        _log(
            db,
            pm.id,
            pm.company_id,
            "AUTO_DISABLED",
            comment=f"连续 {AUTO_DISABLE_THRESHOLD} 张工单无人响应，自动停用",
        )
        db.commit()
        db.refresh(pm)
        return True
    return False


def upcoming_candidates(db: Session, *, today: date, horizon: int) -> list[str]:
    """跨租户取"即将到期但尚未到期"的启用 PM id（调用方需 bypass_tenant_scope）。

    today < next_due_date <= today+horizon。horizon<=0 时返回空（公司未开提醒）。"""
    if horizon <= 0:
        return []
    from datetime import timedelta

    cutoff = today + timedelta(days=horizon)
    stmt = (
        select(PreventiveMaintenance.id)
        .where(
            PreventiveMaintenance.is_active.is_(True),
            PreventiveMaintenance.is_enabled.is_(True),
            PreventiveMaintenance.next_due_date > today,
            PreventiveMaintenance.next_due_date <= cutoff,
        )
        .order_by(PreventiveMaintenance.custom_id)
    )
    return list(db.execute(stmt).scalars().all())


def generate_once(
    db: Session,
    pm: PreventiveMaintenance,
    *,
    actor_user_id: str | None,
    now: datetime,
    enforce_due: bool,
) -> WorkOrder | None:
    """生成一张工单（复制预设）并锥摆推进 next_due_date。返回 WorkOrder。

    调度任务 enforce_due=True（校验到期）；手动端点 enforce_due=False（允许提前）。
    调度路径下若触发 ends_on 终止或失效自停，则不生成并返回 None。
    工单服务在函数内 import 避免模块级循环依赖。
    """
    from datetime import timedelta

    from app.schemas.work_order import WorkOrderCreate
    from app.services import work_order_execution_service as exe
    from app.services import work_order_service as wos

    today = now.date()
    if enforce_due and not (pm.is_active and pm.is_enabled and pm.next_due_date <= today):
        raise bad_request("PM_NOT_DUE", "PM 未到期")

    # ends_on 终止：next_due_date 超过结束日则停止再生成并自动停用（仅调度路径）。
    if enforce_due and pm.ends_on is not None and pm.next_due_date > pm.ends_on:
        pm.is_enabled = False
        _log(db, pm.id, pm.company_id, "ENDED", comment=f"已过结束日 {pm.ends_on.isoformat()}")
        db.commit()
        db.refresh(pm)
        return None

    # 失效自停：评估上一张自动生成的工单是否无人响应，更新连续计数；
    # 达阈值则停用并跳过本次生成（仅调度路径 enforce_due=True 评估，手动路径不计）。
    if enforce_due and _evaluate_auto_disable(db, pm, now=now):
        return None

    # 工单 due_date = 生成日 + due_date_delay 天（表达"给 N 天完成"）。
    generated_due = today + timedelta(days=pm.due_date_delay)
    wo_payload = WorkOrderCreate(
        title=pm.title,
        description=pm.description,
        priority=pm.priority,
        due_date=generated_due,
        asset_id=pm.asset_id,
        location_id=pm.location_id,
        primary_user_id=pm.primary_user_id,
        assignee_ids=assignee_ids(db, pm.id),
        team_ids=team_ids(db, pm.id),
    )
    wo = wos.create_work_order(db, wo_payload, pm.company_id, actor_user_id=actor_user_id)
    if pm.procedure_id is not None:
        exe.attach_procedure(db, wo, pm.procedure_id, pm.company_id, actor_user_id=actor_user_id)
    pm.last_generated_at = now
    pm.last_work_order_id = wo.id
    _log(
        db, pm.id, pm.company_id, "WO_GENERATED", actor_user_id=actor_user_id, comment=wo.custom_id
    )
    pm.next_due_date = _advance_due(
        pm.next_due_date, pm.frequency_unit, pm.frequency_value, today=today
    )
    from app.services import notification_service as _notif

    _notif.on_wo_auto_generated(db, wo, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(pm)
    db.refresh(wo)
    return wo
