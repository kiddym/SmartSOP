"""备件消耗 API（/api/v1/work-orders/{wo_id}/part-consumptions）。独立 router，不改 work_orders.py。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.part_consumption import PartConsumption
from app.models.user import User
from app.models.work_order import WorkOrder
from app.schemas.part import PartConsumptionCreate, PartConsumptionRead
from app.services import part_consumption_service as svc
from app.services import part_service as ps
from app.services import work_order_service as wos

router = APIRouter(
    prefix="/api/v1/work-orders/{work_order_id}/part-consumptions", tags=["part-consumptions"]
)


def _ensure_wo(db: Session, work_order_id: str, company_id: str) -> WorkOrder:
    wo = wos.get_work_order(db, work_order_id)
    if wo is None or wo.company_id != company_id:
        raise not_found("WORKORDER_NOT_FOUND", "工单不存在")
    return wo


@router.get("", response_model=list[PartConsumptionRead])
def list_consumptions(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_VIEW)),
) -> list[PartConsumption]:
    _ensure_wo(db, work_order_id, current_user.company_id)
    return svc.list_consumptions(db, work_order_id)


@router.post("", response_model=PartConsumptionRead, status_code=status.HTTP_201_CREATED)
def consume(
    work_order_id: str,
    payload: PartConsumptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_CONSUME)),
) -> PartConsumption:
    wo = _ensure_wo(db, work_order_id, current_user.company_id)
    part = ps.get_part(db, payload.part_id)
    if part is None or part.company_id != current_user.company_id:
        raise not_found("PART_NOT_FOUND", "备件不存在")
    return svc.consume_part(
        db, wo, part, payload.quantity, current_user.company_id, actor_user_id=current_user.id
    )
