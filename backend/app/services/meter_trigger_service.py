"""仪表触发器服务：边沿评估纯函数、触发器 CRUD、按 trigger 生单。

读数提交时由 meter_service 调用：_condition_met 判定阈值，_decide 给出
FIRE/REARM/NOOP；FIRE 走 generate_from_trigger 复用工单服务。
工单服务在函数内 import 避免循环依赖。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.meter_comparator import MeterComparator
from app.models.meter_trigger import (
    MeterTrigger,
    MeterTriggerAssignee,
    MeterTriggerTeam,
)
from app.schemas.meter import TriggerCreate, TriggerUpdate


def _condition_met(comparator: MeterComparator, value: Decimal, threshold: Decimal) -> bool:
    """严格不等：MORE_THAN→value>threshold；LESS_THAN→value<threshold。相等不算满足。"""
    if comparator == MeterComparator.MORE_THAN:
        return value > threshold
    return value < threshold


def _decide(*, is_armed: bool, met: bool) -> str:
    """边沿状态机：满足且武装→FIRE；未满足且已解武装→REARM；其余 NOOP。"""
    if met and is_armed:
        return "FIRE"
    if (not met) and (not is_armed):
        return "REARM"
    return "NOOP"


def assignee_ids(db: Session, trigger_id: str) -> list[str]:
    return list(db.execute(
        select(MeterTriggerAssignee.user_id)
        .where(MeterTriggerAssignee.trigger_id == trigger_id)
        .order_by(MeterTriggerAssignee.user_id)).scalars().all())


def team_ids(db: Session, trigger_id: str) -> list[str]:
    return list(db.execute(
        select(MeterTriggerTeam.team_id)
        .where(MeterTriggerTeam.trigger_id == trigger_id)
        .order_by(MeterTriggerTeam.team_id)).scalars().all())


def _set_relations(db: Session, trigger_id: str, company_id: str,
                   user_ids: list[str], team_id_list: list[str]) -> None:
    for uid in dict.fromkeys(user_ids):
        db.add(MeterTriggerAssignee(trigger_id=trigger_id, user_id=uid, company_id=company_id))
    for tid in dict.fromkeys(team_id_list):
        db.add(MeterTriggerTeam(trigger_id=trigger_id, team_id=tid, company_id=company_id))


def create_trigger(db: Session, meter_id: str, payload: TriggerCreate, company_id: str,
                   actor_user_id: str | None) -> MeterTrigger:
    trig = MeterTrigger(
        meter_id=meter_id, name=payload.name, comparator=payload.comparator,
        threshold=payload.threshold, priority=payload.priority, title=payload.title,
        description=payload.description, primary_user_id=payload.primary_user_id,
        procedure_id=payload.procedure_id, company_id=company_id,
    )
    db.add(trig)
    db.flush()
    _set_relations(db, trig.id, company_id, payload.assignee_ids, payload.team_ids)
    db.commit()
    db.refresh(trig)
    return trig


def list_triggers(db: Session, meter_id: str) -> list[MeterTrigger]:
    return list(db.execute(
        select(MeterTrigger).where(
            MeterTrigger.meter_id == meter_id,
            MeterTrigger.is_active.is_(True),
        ).order_by(MeterTrigger.created_at, MeterTrigger.id)).scalars().all())


def get_trigger(db: Session, trigger_id: str) -> MeterTrigger | None:
    t = db.get(MeterTrigger, trigger_id)
    if t is None or not t.is_active:
        return None
    return t


def update_trigger(db: Session, trig: MeterTrigger, payload: TriggerUpdate, company_id: str,
                   actor_user_id: str | None) -> MeterTrigger:
    data = payload.model_dump(exclude_unset=True)
    new_assignees = data.pop("assignee_ids", None)
    new_teams = data.pop("team_ids", None)
    for k, v in data.items():
        setattr(trig, k, v)
    if "threshold" in data or "comparator" in data:   # 改阈值/比较符 -> 重新武装
        trig.is_armed = True
    if new_assignees is not None:
        db.execute(MeterTriggerAssignee.__table__.delete()
                   .where(MeterTriggerAssignee.trigger_id == trig.id))
        for uid in dict.fromkeys(new_assignees):
            db.add(MeterTriggerAssignee(trigger_id=trig.id, user_id=uid, company_id=company_id))
    if new_teams is not None:
        db.execute(MeterTriggerTeam.__table__.delete()
                   .where(MeterTriggerTeam.trigger_id == trig.id))
        for tid in dict.fromkeys(new_teams):
            db.add(MeterTriggerTeam(trigger_id=trig.id, team_id=tid, company_id=company_id))
    db.commit()
    db.refresh(trig)
    return trig


def delete_trigger(db: Session, trig: MeterTrigger) -> None:
    trig.is_active = False
    trig.deleted_at = utcnow()
    db.commit()


def enable_trigger(db: Session, trig: MeterTrigger, company_id: str,
                   actor_user_id: str | None) -> MeterTrigger:
    trig.is_enabled = True
    db.commit()
    db.refresh(trig)
    return trig


def disable_trigger(db: Session, trig: MeterTrigger, company_id: str,
                    actor_user_id: str | None) -> MeterTrigger:
    trig.is_enabled = False
    db.commit()
    db.refresh(trig)
    return trig


def generate_from_trigger(db: Session, trig: MeterTrigger, *, reading,
                          actor_user_id: str | None):
    """复制 trigger 预设生成工单，置 last_* 并解除武装。返回 WorkOrder。

    工单服务在函数内 import 避免模块级循环依赖。due_date 留空（反应式工单）。
    create_work_order 内部 commit；trigger 字段变更随调用方末尾 commit 落地。
    """
    from app.schemas.work_order import WorkOrderCreate
    from app.services import work_order_execution_service as exe
    from app.services import work_order_service as wos

    wo_payload = WorkOrderCreate(
        title=trig.title, description=trig.description, priority=trig.priority,
        due_date=None, asset_id=None, location_id=None,
        primary_user_id=trig.primary_user_id,
        assignee_ids=assignee_ids(db, trig.id), team_ids=team_ids(db, trig.id),
    )
    wo = wos.create_work_order(db, wo_payload, trig.company_id, actor_user_id=actor_user_id)
    if trig.procedure_id is not None:
        exe.attach_procedure(db, wo, trig.procedure_id, trig.company_id,
                             actor_user_id=actor_user_id)
    trig.last_triggered_at = reading.reading_at
    trig.last_work_order_id = wo.id
    trig.is_armed = False
    return wo
