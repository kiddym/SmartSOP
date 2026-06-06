"""工单 API（/api/v1/work-orders，含 SOP 执行子资源）。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import forbidden, not_found
from app.models.user import User
from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_step_result import WorkOrderStepResult
from app.schemas.work_order import (
    ActivityRead,
    AssigneesSet,
    AttachProcedure,
    CalendarEvent,
    CommentCreate,
    ExecutionView,
    StepResultUpdate,
    TeamsSet,
    WorkOrderCreate,
    WorkOrderRead,
    WorkOrderRelationCreate,
    WorkOrderRelationRead,
    WorkOrderTransition,
    WorkOrderUpdate,
)
from app.services import work_order_execution_service as exe
from app.services import work_order_service as svc
from app.services.pdf import work_order_report as report

router = APIRouter(prefix="/api/v1/work-orders", tags=["work-orders"])


def _ensure(wo: WorkOrder | None, company_id: str) -> WorkOrder:
    if wo is None or wo.company_id != company_id:
        raise not_found("WORKORDER_NOT_FOUND", "工单不存在")
    return wo


def _ensure_step(
    sr: WorkOrderStepResult | None, work_order_id: str, company_id: str
) -> WorkOrderStepResult:
    if sr is None or sr.work_order_id != work_order_id or sr.company_id != company_id:
        raise not_found("STEP_RESULT_NOT_FOUND", "执行步骤不存在")
    return sr


@router.get("", response_model=list[WorkOrderRead])
def list_work_orders(
    status: str | None = None,
    priority: str | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    assignee_id: str | None = None,
    procedure_attached: bool | None = None,
    part_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[dict[str, object]]:
    rows = svc.list_work_orders(
        db,
        status=status,
        priority=priority,
        asset_id=asset_id,
        location_id=location_id,
        assignee_id=assignee_id,
        procedure_attached=procedure_attached,
        part_id=part_id,
    )
    return [svc.to_read(db, w, viewer=current_user) for w in rows]


# 注：/urgent-count 须注册在 /{work_order_id} 之前，否则会被路径参数吞掉
@router.get("/urgent-count")
def urgent_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> dict[str, int]:
    return {"count": svc.urgent_count(db)}


# 注：/events 须注册在 /{work_order_id} 之前，否则会被路径参数吞掉
@router.get("/events", response_model=list[CalendarEvent])
def calendar_events(
    start: date,
    end: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[dict[str, object]]:
    return svc.calendar_events(db, start=start, end=end)


@router.post("", response_model=WorkOrderRead, status_code=201)
def create_work_order(
    payload: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CREATE)),
) -> dict[str, object]:
    wo = svc.create_work_order(db, payload, current_user.company_id, actor_user_id=current_user.id)
    if payload.procedure_id is not None:
        exe.attach_procedure(
            db, wo, payload.procedure_id, current_user.company_id, actor_user_id=current_user.id
        )
    return svc.to_read(db, wo, viewer=current_user)


@router.get("/{work_order_id}", response_model=WorkOrderRead)
def get_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return svc.to_read(db, wo, viewer=current_user)


@router.get("/{work_order_id}/report")
def work_order_report(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> Response:
    """生成并下载工单 PDF 报告（当前租户）。"""
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    pdf_bytes, filename = report.generate_work_order_report(db, wo)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{work_order_id}", response_model=WorkOrderRead)
def update_work_order(
    work_order_id: str,
    payload: WorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    if not svc.can_edit_work_order(db, current_user, wo):
        raise forbidden("WORKORDER_NOT_EDITABLE", "无权编辑该工单")
    wo = svc.update_work_order(db, wo, payload, current_user.company_id)
    return svc.to_read(db, wo, viewer=current_user)


@router.delete("/{work_order_id}", status_code=204, response_model=None)
def delete_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_DELETE)),
) -> None:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    svc.delete_work_order(db, wo)


@router.put("/{work_order_id}/assignees", response_model=WorkOrderRead)
def set_assignees(
    work_order_id: str,
    payload: AssigneesSet,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = svc.set_assignees(
        db, wo, payload.user_ids, current_user.company_id, actor_user_id=current_user.id
    )
    return svc.to_read(db, wo, viewer=current_user)


@router.put("/{work_order_id}/teams", response_model=WorkOrderRead)
def set_teams(
    work_order_id: str,
    payload: TeamsSet,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = svc.set_teams(
        db, wo, payload.team_ids, current_user.company_id, actor_user_id=current_user.id
    )
    return svc.to_read(db, wo, viewer=current_user)


@router.post("/{work_order_id}/transition", response_model=WorkOrderRead)
def transition(
    work_order_id: str,
    payload: WorkOrderTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = svc.transition(db, wo, payload, current_user.company_id, actor_user_id=current_user.id)
    return svc.to_read(db, wo, viewer=current_user)


@router.post("/{work_order_id}/attach-procedure", response_model=WorkOrderRead)
def attach_procedure(
    work_order_id: str,
    payload: AttachProcedure,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = exe.attach_procedure(
        db, wo, payload.procedure_id, current_user.company_id, actor_user_id=current_user.id
    )
    return svc.to_read(db, wo, viewer=current_user)


@router.delete("/{work_order_id}/procedure", response_model=WorkOrderRead)
def detach_procedure(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = exe.detach_procedure(db, wo, current_user.company_id)
    return svc.to_read(db, wo, viewer=current_user)


@router.get("/{work_order_id}/execution", response_model=ExecutionView)
def execution_view(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return exe.execution_view(db, wo)


@router.patch("/{work_order_id}/steps/{result_id}", response_model=ExecutionView)
def update_step(
    work_order_id: str,
    result_id: str,
    payload: StepResultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EXECUTE)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    sr = _ensure_step(exe.get_step_result(db, result_id), work_order_id, current_user.company_id)
    exe.update_step(db, wo, sr, payload, current_user.company_id, actor_user_id=current_user.id)
    return exe.execution_view(db, wo)


@router.get("/{work_order_id}/relations", response_model=list[WorkOrderRelationRead])
def list_relations(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[dict[str, object]]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return svc.list_relations(db, wo)


@router.post("/{work_order_id}/relations", response_model=WorkOrderRelationRead, status_code=201)
def create_relation(
    work_order_id: str,
    payload: WorkOrderRelationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> dict[str, object]:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    rel = svc.create_relation(
        db,
        wo,
        payload.target_work_order_id,
        payload.relation_type,
        current_user.company_id,
        actor_user_id=current_user.id,
    )
    return svc.relation_to_dict(db, wo, rel)


@router.delete("/{work_order_id}/relations/{relation_id}", status_code=204, response_model=None)
def delete_relation(
    work_order_id: str,
    relation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> None:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    svc.delete_relation(db, wo, relation_id, current_user.company_id)


@router.get("/{work_order_id}/activities", response_model=list[ActivityRead])
def list_activities(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[WorkOrderActivity]:
    _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return svc.list_activities(db, work_order_id)


@router.post("/{work_order_id}/activities", response_model=ActivityRead, status_code=201)
def add_comment(
    work_order_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> WorkOrderActivity:
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return svc.add_comment(
        db, wo, payload.comment, current_user.company_id, actor_user_id=current_user.id
    )
