"""请求服务：CRUD、customId、状态转移（拒绝/取消）、活动时间线。

审批转工单逻辑见本文件 approve_request（复用工单服务）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.base import utcnow
from app.models.request import Request
from app.models.request_activity import RequestActivity
from app.models.request_status import RequestStatus, can_transition
from app.schemas.request import RequestApprove, RequestCreate, RequestUpdate
from app.schemas.work_order import WorkOrderCreate
from app.services import sequence_service


def _log(
    db: Session,
    request_id: str,
    company_id: str,
    activity_type: str,
    actor_user_id: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    comment: str = "",
) -> None:
    db.add(
        RequestActivity(
            request_id=request_id,
            company_id=company_id,
            activity_type=activity_type,
            actor_user_id=actor_user_id,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
        )
    )


def create_request(
    db: Session, payload: RequestCreate, company_id: str, actor_user_id: str | None
) -> Request:
    seq = sequence_service.next_value(db, "request", company_id)
    r = Request(
        custom_id=sequence_service.format_custom_id("RQ", seq),
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=payload.due_date,
        asset_id=payload.asset_id,
        location_id=payload.location_id,
        company_id=company_id,
    )
    db.add(r)
    db.flush()
    from app.services import notification_service as _notif

    _notif.on_request_submitted(db, r, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(r)
    return r


def list_requests(
    db: Session,
    *,
    status: str | None = None,
    priority: str | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
) -> list[Request]:
    stmt = select(Request).where(Request.is_active.is_(True))
    if status is not None:
        stmt = stmt.where(Request.status == status)
    if priority is not None:
        stmt = stmt.where(Request.priority == priority)
    if asset_id is not None:
        stmt = stmt.where(Request.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(Request.location_id == location_id)
    return list(db.execute(stmt.order_by(Request.custom_id)).scalars().all())


def get_request(db: Session, request_id: str) -> Request | None:
    r = db.get(Request, request_id)
    if r is None or not r.is_active:
        return None
    return r


def _assert_pending(r: Request) -> None:
    if r.status != RequestStatus.PENDING:
        raise bad_request("REQUEST_NOT_PENDING", "请求已处理，不可再操作")


def update_request(db: Session, r: Request, payload: RequestUpdate) -> Request:
    _assert_pending(r)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


def _resolve(
    db: Session,
    r: Request,
    dst: RequestStatus,
    reason: str,
    company_id: str,
    actor_user_id: str | None,
) -> Request:
    if not can_transition(r.status, dst):
        raise bad_request("REQUEST_BAD_TRANSITION", f"非法状态转移 {r.status.value}->{dst.value}")
    r.status = dst
    r.resolution_note = reason
    r.resolved_by_user_id = actor_user_id
    r.resolved_at = utcnow()
    _log(
        db,
        r.id,
        company_id,
        "STATUS_CHANGE",
        actor_user_id=actor_user_id,
        from_status=RequestStatus.PENDING.value,
        to_status=dst.value,
        comment=reason,
    )
    db.commit()
    db.refresh(r)
    return r


def reject_request(
    db: Session, r: Request, reason: str, company_id: str, actor_user_id: str | None
) -> Request:
    return _resolve(db, r, RequestStatus.REJECTED, reason, company_id, actor_user_id)


def cancel_request(
    db: Session, r: Request, reason: str, company_id: str, actor_user_id: str | None
) -> Request:
    return _resolve(db, r, RequestStatus.CANCELED, reason, company_id, actor_user_id)


def delete_request(db: Session, r: Request) -> None:
    r.is_active = False
    r.deleted_at = utcnow()
    db.commit()


def add_comment(
    db: Session, r: Request, comment: str, company_id: str, actor_user_id: str | None
) -> RequestActivity:
    act = RequestActivity(
        request_id=r.id,
        company_id=company_id,
        activity_type="COMMENT",
        actor_user_id=actor_user_id,
        comment=comment,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def list_activities(db: Session, request_id: str) -> list[RequestActivity]:
    return list(
        db.execute(
            select(RequestActivity)
            .where(RequestActivity.request_id == request_id)
            .order_by(RequestActivity.created_at, RequestActivity.id)
        )
        .scalars()
        .all()
    )


def approve_request(
    db: Session, r: Request, payload: RequestApprove, company_id: str, actor_user_id: str | None
):
    """审批通过：复制请求字段生成工单（可附加指派/SOP），双向弱关联。返回生成的 WorkOrder。

    工单服务在函数内部 import 以避免模块级循环依赖。
    """
    from app.services import work_order_execution_service as exe
    from app.services import work_order_service as wos

    if not can_transition(r.status, RequestStatus.APPROVED):
        raise bad_request("REQUEST_BAD_TRANSITION", f"非法状态转移 {r.status.value}->APPROVED")
    wo_payload = WorkOrderCreate(
        title=r.title,
        description=r.description,
        priority=r.priority,
        due_date=r.due_date,
        asset_id=r.asset_id,
        location_id=r.location_id,
        primary_user_id=payload.primary_user_id,
        assignee_ids=payload.assignee_ids,
        team_ids=payload.team_ids,
    )
    wo = wos.create_work_order(db, wo_payload, company_id, actor_user_id=actor_user_id)
    if payload.procedure_id is not None:
        exe.attach_procedure(db, wo, payload.procedure_id, company_id, actor_user_id=actor_user_id)
    wo.request_id = r.id
    r.status = RequestStatus.APPROVED
    r.work_order_id = wo.id
    r.resolved_by_user_id = actor_user_id
    r.resolved_at = utcnow()
    _log(
        db,
        r.id,
        company_id,
        "STATUS_CHANGE",
        actor_user_id=actor_user_id,
        from_status=RequestStatus.PENDING.value,
        to_status=RequestStatus.APPROVED.value,
        comment=payload.note,
    )
    _log(db, r.id, company_id, "WO_GENERATED", actor_user_id=actor_user_id, comment=wo.custom_id)
    db.commit()
    db.refresh(r)
    db.refresh(wo)
    return wo
