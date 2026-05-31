"""站内通知生成服务（Phase 5A）。

附加式观察者：notify(...) 仅向 session add 行，由调用方所在事务提交。
接收人解析复用 permissions.effective_codes；边沿原语 arm/disarm 仿 meter is_armed。
所有查询显式按 company_id 过滤（不依赖租户事件），以便调度 tick 下也正确。
"""
from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm
from app.models.role import Role
from app.models.team import TeamUser
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.permissions import effective_codes


# --------------------------------------------------------------------------- #
# 落行
# --------------------------------------------------------------------------- #
def notify(
    db: Session, *, company_id: str, recipient_ids: set[str], type: str,
    entity_type: str | None, entity_id: str | None, params: dict,
    actor_user_id: str | None = None, dedup_key: str | None = None,
) -> int:
    """每个收件人 add 一行 Notification（不 commit）。返回新增行数。"""
    payload = json.dumps(params, ensure_ascii=False, default=str)
    count = 0
    for uid in recipient_ids:
        db.add(Notification(
            company_id=company_id, recipient_user_id=uid, type=type,
            entity_type=entity_type, entity_id=entity_id, params=payload,
            actor_user_id=actor_user_id, dedup_key=dedup_key,
        ))
        count += 1
    return count


# --------------------------------------------------------------------------- #
# 接收人解析
# --------------------------------------------------------------------------- #
def _active_subset(db: Session, company_id: str, ids: set[str],
                   exclude_actor_id: str | None) -> set[str]:
    if not ids:
        return set()
    rows = db.execute(
        select(User.id).where(
            User.company_id == company_id, User.id.in_(ids),
            User.status == UserStatus.active,
        )
    ).all()
    out = {r for (r,) in rows}
    if exclude_actor_id is not None:
        out.discard(exclude_actor_id)
    return out


def resolve_team_members(db: Session, company_id: str, team_ids: set[str]) -> set[str]:
    if not team_ids:
        return set()
    rows = db.execute(
        select(TeamUser.user_id).where(
            TeamUser.company_id == company_id, TeamUser.team_id.in_(team_ids)
        )
    ).all()
    return {r for (r,) in rows}


def resolve_wo_recipients(db: Session, wo: WorkOrder, *,
                          exclude_actor_id: str | None) -> set[str]:
    ids: set[str] = set()
    if wo.primary_user_id:
        ids.add(wo.primary_user_id)
    assignees = db.execute(
        select(WorkOrderAssignee.user_id).where(WorkOrderAssignee.work_order_id == wo.id)
    ).all()
    ids |= {r for (r,) in assignees}
    teams = db.execute(
        select(WorkOrderTeam.team_id).where(WorkOrderTeam.work_order_id == wo.id)
    ).all()
    ids |= resolve_team_members(db, wo.company_id, {r for (r,) in teams})
    return _active_subset(db, wo.company_id, ids, exclude_actor_id)


def resolve_permission_holders(db: Session, company_id: str, code: str, *,
                               exclude_actor_id: str | None) -> set[str]:
    rows = db.execute(
        select(User.id, Role.code, Role.permissions)
        .join(Role, User.role_id == Role.id, isouter=True)
        .where(User.company_id == company_id, User.status == UserStatus.active)
    ).all()
    out: set[str] = set()
    for uid, role_code, perms in rows:
        if code in effective_codes(role_code or "", perms or []):
            out.add(uid)
    if exclude_actor_id is not None:
        out.discard(exclude_actor_id)
    return out


def active_admins(db: Session, company_id: str) -> set[str]:
    rows = db.execute(
        select(User.id)
        .join(Role, User.role_id == Role.id)
        .where(User.company_id == company_id, User.status == UserStatus.active,
               Role.code.in_(["admin", "super_admin"]))
    ).all()
    return {r for (r,) in rows}


# --------------------------------------------------------------------------- #
# 边沿原语
# --------------------------------------------------------------------------- #
def is_armed(db: Session, company_id: str, key: str) -> bool:
    row = db.execute(
        select(NotificationArm.id).where(
            NotificationArm.company_id == company_id, NotificationArm.key == key
        )
    ).first()
    return row is not None


def arm(db: Session, company_id: str, key: str) -> None:
    db.add(NotificationArm(company_id=company_id, key=key))


def disarm(db: Session, company_id: str, key: str) -> None:
    db.execute(
        delete(NotificationArm).where(
            NotificationArm.company_id == company_id, NotificationArm.key == key
        )
    )
