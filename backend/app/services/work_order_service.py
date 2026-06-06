"""工单服务：CRUD、customId、指派、状态转移、活动时间线。

SOP 执行相关逻辑见 work_order_execution_service。挂接了 SOP 的工单转
COMPLETE 的 step 完成校验也在 execution service（避免循环依赖：本模块在
transition 时按需 import）。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict, not_found, unprocessable
from app.models.base import utcnow
from app.models.part_consumption import PartConsumption
from app.models.role import Role
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderRelation, WorkOrderTeam
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_category import WorkOrderCategory
from app.models.work_order_status import (
    SYMMETRIC_RELATION_TYPES,
    WorkOrderRelationType,
    WorkOrderStatus,
    can_transition,
)
from app.schemas.work_order import WorkOrderCreate, WorkOrderTransition, WorkOrderUpdate
from app.services import notification_service as _notif
from app.services import sequence_service


def _validate_category(db: Session, category_id: str | None, company_id: str) -> None:
    if category_id is None:
        return
    cat = db.get(WorkOrderCategory, category_id)
    if cat is None or not cat.is_active or cat.company_id != company_id:
        raise not_found("WORK_ORDER_CATEGORY_NOT_FOUND", "工单分类不存在")


def assignee_ids(db: Session, work_order_id: str) -> list[str]:
    return list(
        db.execute(
            select(WorkOrderAssignee.user_id).where(
                WorkOrderAssignee.work_order_id == work_order_id
            )
        )
        .scalars()
        .all()
    )


def team_ids(db: Session, work_order_id: str) -> list[str]:
    return list(
        db.execute(
            select(WorkOrderTeam.team_id).where(WorkOrderTeam.work_order_id == work_order_id)
        )
        .scalars()
        .all()
    )


def can_edit_work_order(db: Session, user: User, wo: WorkOrder) -> bool:
    """对象级可编辑谓词：角色 → 终态锁 → 归属。仅用于 PATCH 字段编辑，不锁 reopen。"""
    role = db.get(Role, user.role_id) if user.role_id else None
    if role is not None and role.code in {"super_admin", "admin"}:
        return True
    if wo.status in {WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELED}:
        return False
    if user.id == wo.created_by_user_id:
        return True
    if user.id == wo.primary_user_id:
        return True
    return user.id in set(assignee_ids(db, wo.id))


def to_read(db: Session, wo: WorkOrder, viewer: User | None = None) -> dict[str, object]:
    return {
        "id": wo.id,
        "custom_id": wo.custom_id,
        "title": wo.title,
        "description": wo.description,
        "status": wo.status,
        "priority": wo.priority,
        "due_date": wo.due_date,
        "asset_id": wo.asset_id,
        "location_id": wo.location_id,
        "primary_user_id": wo.primary_user_id,
        "procedure_id": wo.procedure_id,
        "procedure_group_id": wo.procedure_group_id,
        "completed_at": wo.completed_at,
        "category_id": wo.category_id,
        "created_by_user_id": wo.created_by_user_id,
        "completed_by_user_id": wo.completed_by_user_id,
        "feedback": wo.feedback,
        "urgent": wo.urgent,
        "estimated_duration": wo.estimated_duration,
        "estimated_start_date": wo.estimated_start_date,
        "first_responded_at": wo.first_responded_at,
        "archived": wo.archived,
        "is_compliant": wo.is_compliant,
        "signature_url": wo.signature_url,
        "required_signature": wo.required_signature,
        "assignee_ids": assignee_ids(db, wo.id),
        "team_ids": team_ids(db, wo.id),
        "can_be_edited": can_edit_work_order(db, viewer, wo) if viewer is not None else False,
    }


def _log(
    db: Session,
    work_order_id: str,
    company_id: str,
    activity_type: str,
    actor_user_id: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    comment: str = "",
) -> None:
    db.add(
        WorkOrderActivity(
            work_order_id=work_order_id,
            company_id=company_id,
            activity_type=activity_type,
            actor_user_id=actor_user_id,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
        )
    )


def set_assignees(
    db: Session,
    wo: WorkOrder,
    user_ids: list[str],
    company_id: str,
    actor_user_id: str | None = None,
) -> WorkOrder:
    prior = {
        r
        for (r,) in db.execute(
            select(WorkOrderAssignee.user_id).where(WorkOrderAssignee.work_order_id == wo.id)
        ).all()
    }
    db.execute(delete(WorkOrderAssignee).where(WorkOrderAssignee.work_order_id == wo.id))
    for uid in dict.fromkeys(user_ids):
        db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=uid, company_id=company_id))
    _log(db, wo.id, company_id, "ASSIGN", actor_user_id=actor_user_id)
    added = set(dict.fromkeys(user_ids)) - prior
    _notif.on_wo_assigned(db, wo, recipient_ids=added, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(wo)
    return wo


def set_teams(
    db: Session,
    wo: WorkOrder,
    team_ids_: list[str],
    company_id: str,
    actor_user_id: str | None = None,
) -> WorkOrder:
    prior = {
        r
        for (r,) in db.execute(
            select(WorkOrderTeam.team_id).where(WorkOrderTeam.work_order_id == wo.id)
        ).all()
    }
    db.execute(delete(WorkOrderTeam).where(WorkOrderTeam.work_order_id == wo.id))
    for tid in dict.fromkeys(team_ids_):
        db.add(WorkOrderTeam(work_order_id=wo.id, team_id=tid, company_id=company_id))
    _log(db, wo.id, company_id, "ASSIGN", actor_user_id=actor_user_id)
    added_teams = set(dict.fromkeys(team_ids_)) - prior
    members = _notif.resolve_team_members(db, company_id, added_teams)
    _notif.on_wo_assigned(db, wo, recipient_ids=members, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(wo)
    return wo


def create_work_order(
    db: Session, payload: WorkOrderCreate, company_id: str, actor_user_id: str | None
) -> WorkOrder:
    # spec §3.4 当前未定义 CREATE 活动类型，建单不写时间线；
    # actor_user_id 用于落 created_by_user_id（创建者归属，供分析归集）。
    _validate_category(db, payload.category_id, company_id)
    seq = sequence_service.next_value(db, "work_order", company_id)
    wo = WorkOrder(
        custom_id=sequence_service.format_custom_id("WO", seq),
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=payload.due_date,
        asset_id=payload.asset_id,
        location_id=payload.location_id,
        primary_user_id=payload.primary_user_id,
        category_id=payload.category_id,
        required_signature=payload.required_signature,
        created_by_user_id=actor_user_id,
        company_id=company_id,
    )
    db.add(wo)
    db.flush()
    for uid in dict.fromkeys(payload.assignee_ids):
        db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=uid, company_id=company_id))
    for tid in dict.fromkeys(payload.team_ids):
        db.add(WorkOrderTeam(work_order_id=wo.id, team_id=tid, company_id=company_id))
    # 工作流引擎：WORK_ORDER_CREATED（同事务、commit 前；引擎仅改字段不递归）
    from app.services import workflow_engine

    workflow_engine.run_for_work_order(db, wo, workflow_engine.WORK_ORDER_CREATED, company_id)
    db.commit()
    db.refresh(wo)
    return wo


def list_work_orders(
    db: Session,
    *,
    status: str | None = None,
    priority: str | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    assignee_id: str | None = None,
    procedure_attached: bool | None = None,
    part_id: str | None = None,
) -> list[WorkOrder]:
    stmt = select(WorkOrder).where(WorkOrder.is_active.is_(True))
    if status is not None:
        stmt = stmt.where(WorkOrder.status == status)
    if priority is not None:
        stmt = stmt.where(WorkOrder.priority == priority)
    if asset_id is not None:
        stmt = stmt.where(WorkOrder.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(WorkOrder.location_id == location_id)
    if procedure_attached is not None:
        if procedure_attached:
            stmt = stmt.where(WorkOrder.procedure_id.is_not(None))
        else:
            stmt = stmt.where(WorkOrder.procedure_id.is_(None))
    if assignee_id is not None:
        sub = select(WorkOrderAssignee.work_order_id).where(
            WorkOrderAssignee.user_id == assignee_id
        )
        stmt = stmt.where(WorkOrder.id.in_(sub))
    if part_id is not None:
        sub = (
            select(PartConsumption.work_order_id)
            .where(PartConsumption.part_id == part_id)
            .distinct()
        )
        stmt = stmt.where(WorkOrder.id.in_(sub))
    return list(db.execute(stmt.order_by(WorkOrder.custom_id)).scalars().all())


_OPEN_WO_STATUSES = (
    WorkOrderStatus.OPEN,
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.ON_HOLD,
)


def urgent_count(db: Session) -> int:
    """当前租户下 urgent=True 且处于未完成/未取消（OPEN/IN_PROGRESS/ON_HOLD）的工单数。"""
    stmt = (
        select(func.count())
        .select_from(WorkOrder)
        .where(
            WorkOrder.is_active.is_(True),
            WorkOrder.urgent.is_(True),
            WorkOrder.status.in_(_OPEN_WO_STATUSES),
        )
    )
    return int(db.execute(stmt).scalar_one())


def calendar_events(db: Session, *, start: date, end: date) -> list[dict[str, object]]:
    """聚合 [start,end] 内的日历事件（当前租户）：

    - 工单：due_date 落在区间的活跃工单 → type=work_order（含 status/priority）。
    - PM：next_due_date 落在区间的活跃且启用 PM → type=pm。

    在 service 层内 import PreventiveMaintenance 避免模块级循环依赖。
    """
    from app.models.preventive_maintenance import PreventiveMaintenance

    events: list[dict[str, object]] = []
    wo_stmt = (
        select(WorkOrder)
        .where(
            WorkOrder.is_active.is_(True),
            WorkOrder.due_date.is_not(None),
            WorkOrder.due_date >= start,
            WorkOrder.due_date <= end,
        )
        .order_by(WorkOrder.due_date, WorkOrder.custom_id)
    )
    for wo in db.execute(wo_stmt).scalars().all():
        events.append(
            {
                "type": "work_order",
                "id": wo.id,
                "custom_id": wo.custom_id,
                "title": wo.title,
                "date": wo.due_date,
                "status": wo.status,
                "priority": wo.priority,
            }
        )
    pm_stmt = (
        select(PreventiveMaintenance)
        .where(
            PreventiveMaintenance.is_active.is_(True),
            PreventiveMaintenance.is_enabled.is_(True),
            PreventiveMaintenance.next_due_date >= start,
            PreventiveMaintenance.next_due_date <= end,
        )
        .order_by(PreventiveMaintenance.next_due_date, PreventiveMaintenance.custom_id)
    )
    for pm in db.execute(pm_stmt).scalars().all():
        events.append(
            {
                "type": "pm",
                "id": pm.id,
                "custom_id": pm.custom_id,
                "title": pm.title,
                "date": pm.next_due_date,
            }
        )
    return events


def get_work_order(db: Session, work_order_id: str) -> WorkOrder | None:
    wo = db.get(WorkOrder, work_order_id)
    if wo is None or not wo.is_active:
        return None
    return wo


def update_work_order(
    db: Session, wo: WorkOrder, payload: WorkOrderUpdate, company_id: str
) -> WorkOrder:
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        _validate_category(db, data["category_id"], company_id)
    for k, v in data.items():
        setattr(wo, k, v)
    db.commit()
    db.refresh(wo)
    return wo


def transition(
    db: Session,
    wo: WorkOrder,
    payload: WorkOrderTransition,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrder:
    src, dst = wo.status, payload.to_status
    if not can_transition(src, dst):
        raise bad_request("WORKORDER_BAD_TRANSITION", f"非法状态转移 {src.value}->{dst.value}")
    # 首次离开 OPEN：戳记首响时间（只记一次，重开不覆盖）
    if src == WorkOrderStatus.OPEN and wo.first_responded_at is None:
        wo.first_responded_at = utcnow()
    if dst == WorkOrderStatus.COMPLETE:
        from app.services import work_order_execution_service as exe

        exe.assert_completable(db, wo)
        # 完成签名：transition payload 可携带 signature_url 存档；
        # required_signature=True 且最终无签名则拒绝完成。
        if payload.signature_url is not None:
            wo.signature_url = payload.signature_url
        if wo.required_signature and not wo.signature_url:
            raise unprocessable("SIGNATURE_REQUIRED", "完成该工单需要签名")
        wo.completed_at = utcnow()
        wo.completed_by_user_id = actor_user_id
        # 合规快照：无截止日视为合规；否则按完成日 <= 截止日
        wo.is_compliant = wo.due_date is None or wo.completed_at.date() <= wo.due_date
    if src == WorkOrderStatus.COMPLETE and dst == WorkOrderStatus.IN_PROGRESS:
        wo.completed_at = None
        wo.completed_by_user_id = None
        wo.is_compliant = None
    wo.status = dst
    _log(
        db,
        wo.id,
        company_id,
        "STATUS_CHANGE",
        actor_user_id=actor_user_id,
        from_status=src.value,
        to_status=dst.value,
        comment=payload.note,
    )
    _notif.on_wo_status_changed(
        db, wo, from_status=src.value, to_status=dst.value, actor_user_id=actor_user_id
    )
    # 工作流引擎：WORK_ORDER_STATUS_CHANGED（针对转移后的新状态评估）。
    # 引擎内 set_status 直改字段、不回调 transition，故不会再触发本工作流（无递归）。
    from app.services import workflow_engine

    workflow_engine.run_for_work_order(
        db, wo, workflow_engine.WORK_ORDER_STATUS_CHANGED, company_id
    )
    db.commit()
    db.refresh(wo)
    return wo


def delete_work_order(db: Session, wo: WorkOrder) -> None:
    wo.is_active = False
    wo.deleted_at = utcnow()
    db.commit()


def add_comment(
    db: Session, wo: WorkOrder, comment: str, company_id: str, actor_user_id: str | None
) -> WorkOrderActivity:
    act = WorkOrderActivity(
        work_order_id=wo.id,
        company_id=company_id,
        activity_type="COMMENT",
        actor_user_id=actor_user_id,
        comment=comment,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def list_activities(db: Session, work_order_id: str) -> list[WorkOrderActivity]:
    return list(
        db.execute(
            select(WorkOrderActivity)
            .where(WorkOrderActivity.work_order_id == work_order_id)
            .order_by(WorkOrderActivity.created_at, WorkOrderActivity.id)
        )
        .scalars()
        .all()
    )


def relation_to_dict(db: Session, wo: WorkOrder, rel: WorkOrderRelation) -> dict[str, object]:
    """Return the relation dict as seen from `wo` (direction, other-WO fields)."""
    is_source = rel.source_work_order_id == wo.id
    other_id = rel.target_work_order_id if is_source else rel.source_work_order_id
    if rel.relation_type in SYMMETRIC_RELATION_TYPES:
        direction = "symmetric"
    else:
        direction = "outgoing" if is_source else "incoming"
    other = db.get(WorkOrder, other_id)
    return {
        "id": rel.id,
        "relation_type": rel.relation_type,
        "direction": direction,
        "related_work_order_id": other_id,
        "related_custom_id": other.custom_id if other else None,
        "related_title": other.title if other else None,
        "related_status": other.status if other else None,
    }


def create_relation(
    db: Session,
    wo: WorkOrder,
    target_id: str,
    relation_type: WorkOrderRelationType,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderRelation:
    if target_id == wo.id:
        raise bad_request("WORKORDER_RELATION_SELF", "不能关联自身")
    target = get_work_order(db, target_id)
    if target is None or target.company_id != company_id:
        raise not_found("WORKORDER_NOT_FOUND", "目标工单不存在")
    # Directional duplicate: exact (source, target, type) pair
    dup = db.execute(
        select(WorkOrderRelation).where(
            WorkOrderRelation.source_work_order_id == wo.id,
            WorkOrderRelation.target_work_order_id == target_id,
            WorkOrderRelation.relation_type == relation_type,
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise conflict("WORKORDER_RELATION_DUPLICATE", "关联已存在")
    # Symmetric reverse-duplicate: for symmetric types, (target→wo) with same type is also a dup
    if relation_type in SYMMETRIC_RELATION_TYPES:
        rev_dup = db.execute(
            select(WorkOrderRelation).where(
                WorkOrderRelation.source_work_order_id == target_id,
                WorkOrderRelation.target_work_order_id == wo.id,
                WorkOrderRelation.relation_type == relation_type,
            )
        ).scalar_one_or_none()
        if rev_dup is not None:
            raise conflict("WORKORDER_RELATION_DUPLICATE", "关联已存在")
    rel = WorkOrderRelation(
        source_work_order_id=wo.id,
        target_work_order_id=target_id,
        relation_type=relation_type,
        created_by_user_id=actor_user_id,
        company_id=company_id,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def list_relations(db: Session, wo: WorkOrder) -> list[dict[str, object]]:
    rels = (
        db.execute(
            select(WorkOrderRelation).where(
                (WorkOrderRelation.source_work_order_id == wo.id)
                | (WorkOrderRelation.target_work_order_id == wo.id)
            )
        )
        .scalars()
        .all()
    )
    return [relation_to_dict(db, wo, r) for r in rels]


def delete_relation(db: Session, wo: WorkOrder, relation_id: str, company_id: str) -> None:
    rel = db.get(WorkOrderRelation, relation_id)
    if (
        rel is None
        or rel.company_id != company_id
        or wo.id not in {rel.source_work_order_id, rel.target_work_order_id}
    ):
        raise not_found("WORKORDER_RELATION_NOT_FOUND", "关联不存在")
    db.delete(rel)
    db.commit()
