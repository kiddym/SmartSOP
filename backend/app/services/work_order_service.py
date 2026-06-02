"""工单服务：CRUD、customId、指派、状态转移、活动时间线。

SOP 执行相关逻辑见 work_order_execution_service。挂接了 SOP 的工单转
COMPLETE 的 step 完成校验也在 execution service（避免循环依赖：本模块在
transition 时按需 import）。
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request, not_found
from app.models.base import utcnow
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_category import WorkOrderCategory
from app.models.work_order_status import WorkOrderStatus, can_transition
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


def to_read(db: Session, wo: WorkOrder) -> dict[str, object]:
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
        "assignee_ids": assignee_ids(db, wo.id),
        "team_ids": team_ids(db, wo.id),
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
        created_by_user_id=actor_user_id,
        company_id=company_id,
    )
    db.add(wo)
    db.flush()
    for uid in dict.fromkeys(payload.assignee_ids):
        db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=uid, company_id=company_id))
    for tid in dict.fromkeys(payload.team_ids):
        db.add(WorkOrderTeam(work_order_id=wo.id, team_id=tid, company_id=company_id))
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
    return list(db.execute(stmt.order_by(WorkOrder.custom_id)).scalars().all())


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
    if dst == WorkOrderStatus.COMPLETE:
        from app.services import work_order_execution_service as exe

        exe.assert_completable(db, wo)
        wo.completed_at = utcnow()
    if src == WorkOrderStatus.COMPLETE and dst == WorkOrderStatus.IN_PROGRESS:
        wo.completed_at = None
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
