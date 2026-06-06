"""站内通知生成服务（Phase 5A）。

附加式观察者：notify(...) 仅向 session add 行，由调用方所在事务提交。
接收人解析复用 permissions.effective_codes；边沿原语 arm/disarm 仿 meter is_armed。
所有查询显式按 company_id 过滤（不依赖租户事件），以便调度 tick 下也正确。
"""

from __future__ import annotations

import json
from typing import Any

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
    db: Session,
    *,
    company_id: str,
    recipient_ids: set[str],
    type: str,
    entity_type: str | None,
    entity_id: str | None,
    params: dict[str, Any],
    actor_user_id: str | None = None,
    dedup_key: str | None = None,
) -> int:
    """每个收件人 add 一行 Notification（不 commit）。返回新增行数。"""
    payload = json.dumps(params, ensure_ascii=False, default=str)
    count = 0
    for uid in recipient_ids:
        db.add(
            Notification(
                company_id=company_id,
                recipient_user_id=uid,
                type=type,
                entity_type=entity_type,
                entity_id=entity_id,
                params=payload,
                actor_user_id=actor_user_id,
                dedup_key=dedup_key,
            )
        )
        count += 1
    # Phase 5B：同事务内按偏好为有邮箱的活跃收件人入队邮件（附加式，不 commit）。
    from app.services import email_outbox_service

    email_outbox_service.enqueue(
        db, company_id=company_id, recipient_ids=set(recipient_ids), type=type, params=params
    )
    return count


# --------------------------------------------------------------------------- #
# 接收人解析
# --------------------------------------------------------------------------- #
def _active_subset(
    db: Session, company_id: str, ids: set[str], exclude_actor_id: str | None
) -> set[str]:
    if not ids:
        return set()
    rows = db.execute(
        select(User.id).where(
            User.company_id == company_id,
            User.id.in_(ids),
            User.status == UserStatus.active,
        )
    ).all()
    out = {r for (r,) in rows}
    if exclude_actor_id is not None:
        out.discard(exclude_actor_id)
    return out


def active_recipient_subset(
    db: Session, company_id: str, ids: set[str], exclude_actor_id: str | None
) -> set[str]:
    """公开包装：过滤出活跃用户子集（供调度任务等模块外部复用）。"""
    return _active_subset(db, company_id, ids, exclude_actor_id)


def resolve_team_members(db: Session, company_id: str, team_ids: set[str]) -> set[str]:
    if not team_ids:
        return set()
    rows = db.execute(
        select(TeamUser.user_id).where(
            TeamUser.company_id == company_id, TeamUser.team_id.in_(team_ids)
        )
    ).all()
    return {r for (r,) in rows}


def resolve_wo_recipients(db: Session, wo: WorkOrder, *, exclude_actor_id: str | None) -> set[str]:
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


def resolve_permission_holders(
    db: Session, company_id: str, code: str, *, exclude_actor_id: str | None
) -> set[str]:
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
        .where(
            User.company_id == company_id,
            User.status == UserStatus.active,
            Role.code.in_(["admin", "super_admin"]),
        )
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


# --------------------------------------------------------------------------- #
# 事件组合（内联调用；均不 commit，由调用方事务提交）
# --------------------------------------------------------------------------- #
def on_wo_assigned(
    db: Session, wo: WorkOrder, *, recipient_ids: set[str], actor_user_id: str | None
) -> None:
    recips = _active_subset(db, wo.company_id, set(recipient_ids), actor_user_id)
    notify(
        db,
        company_id=wo.company_id,
        recipient_ids=recips,
        type="WO_ASSIGNED",
        entity_type="work_order",
        entity_id=wo.id,
        params={"custom_id": wo.custom_id, "title": wo.title},
        actor_user_id=actor_user_id,
    )


def on_wo_status_changed(
    db: Session, wo: WorkOrder, *, from_status: str, to_status: str, actor_user_id: str | None
) -> None:
    recips = resolve_wo_recipients(db, wo, exclude_actor_id=actor_user_id)
    notify(
        db,
        company_id=wo.company_id,
        recipient_ids=recips,
        type="WO_STATUS_CHANGED",
        entity_type="work_order",
        entity_id=wo.id,
        params={"custom_id": wo.custom_id, "from_status": from_status, "to_status": to_status},
        actor_user_id=actor_user_id,
    )


def on_wo_auto_generated(db: Session, wo: WorkOrder, *, actor_user_id: str | None) -> None:
    recips = resolve_wo_recipients(db, wo, exclude_actor_id=actor_user_id)
    if not recips:
        recips = active_admins(db, wo.company_id)
        if actor_user_id is not None:
            recips.discard(actor_user_id)
    notify(
        db,
        company_id=wo.company_id,
        recipient_ids=recips,
        type="WO_AUTO_GENERATED",
        entity_type="work_order",
        entity_id=wo.id,
        params={"custom_id": wo.custom_id, "title": wo.title},
        actor_user_id=actor_user_id,
    )


def on_request_submitted(db: Session, request: Any, *, actor_user_id: str | None) -> None:
    recips = resolve_permission_holders(
        db, request.company_id, "request.approve", exclude_actor_id=actor_user_id
    )
    notify(
        db,
        company_id=request.company_id,
        recipient_ids=recips,
        type="REQUEST_SUBMITTED",
        entity_type="request",
        entity_id=request.id,
        params={"custom_id": request.custom_id, "title": request.title},
        actor_user_id=actor_user_id,
    )


def on_po_submitted(db: Session, po: Any, *, actor_user_id: str | None) -> None:
    _notify_po(db, po, "PO_SUBMITTED", actor_user_id)


def on_po_approved(db: Session, po: Any, *, actor_user_id: str | None) -> None:
    _notify_po(db, po, "PO_APPROVED", actor_user_id)


def _notify_po(db: Session, po: Any, type_: str, actor_user_id: str | None) -> None:
    recips = resolve_permission_holders(
        db, po.company_id, "purchase_order.approve", exclude_actor_id=actor_user_id
    )
    notify(
        db,
        company_id=po.company_id,
        recipient_ids=recips,
        type=type_,
        entity_type="purchase_order",
        entity_id=po.id,
        params={"custom_id": po.custom_id},
        actor_user_id=actor_user_id,
    )
