"""工单成本子资源 API（/api/v1/work-orders/{id}）：工时 / 额外成本 / 总成本汇总。

独立 router，不改 work_orders.py（照 part_consumptions.py 子资源模式）。
读=work_order.view，写=work_order.edit。

额外成本（AdditionalCost）与总成本汇总（CostSummary）端点后续 Task 4/5 加入本文件。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_labor import WorkOrderLabor
from app.schemas.work_order_cost import (
    AdditionalCostCreate,
    AdditionalCostRead,
    AdditionalCostUpdate,
    CostSummaryRead,
    LaborCreate,
    LaborRead,
    LaborTimerStart,
    LaborUpdate,
)
from app.services import work_order_additional_cost_service as addcost
from app.services import work_order_cost_service as costsvc
from app.services import work_order_labor_service as labor
from app.services import work_order_service as wos

router = APIRouter(prefix="/api/v1/work-orders/{work_order_id}", tags=["work-order-costs"])


def _ensure_wo(db: Session, work_order_id: str, company_id: str) -> WorkOrder:
    wo = wos.get_work_order(db, work_order_id)
    if wo is None or wo.company_id != company_id:
        raise not_found("WORKORDER_NOT_FOUND", "工单不存在")
    return wo


def _ensure_labor(
    db: Session,
    labor_id: str,
    work_order_id: str,
    company_id: str,
) -> WorkOrderLabor:
    row = db.get(WorkOrderLabor, labor_id)
    if (
        row is None
        or row.work_order_id != work_order_id
        or row.company_id != company_id
    ):
        raise not_found("LABOR_NOT_FOUND", "工时记录不存在")
    return row


@router.get("/labor", response_model=list[LaborRead])
def list_labor(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[WorkOrderLabor]:
    _ensure_wo(db, work_order_id, current_user.company_id)
    return labor.list_labor(db, work_order_id)


@router.post("/labor/start", response_model=LaborRead, status_code=status.HTTP_201_CREATED)
def start_timer(
    work_order_id: str,
    payload: LaborTimerStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderLabor:
    wo = _ensure_wo(db, work_order_id, current_user.company_id)
    return labor.start_timer(
        db, wo, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.post("/labor", response_model=LaborRead, status_code=status.HTTP_201_CREATED)
def create_labor(
    work_order_id: str,
    payload: LaborCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderLabor:
    wo = _ensure_wo(db, work_order_id, current_user.company_id)
    return labor.create_labor(
        db, wo, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.post("/labor/{labor_id}/stop", response_model=LaborRead)
def stop_timer(
    work_order_id: str,
    labor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderLabor:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_labor(db, labor_id, work_order_id, current_user.company_id)
    return labor.stop_timer(db, row)


@router.patch("/labor/{labor_id}", response_model=LaborRead)
def update_labor(
    work_order_id: str,
    labor_id: str,
    payload: LaborUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderLabor:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_labor(db, labor_id, work_order_id, current_user.company_id)
    return labor.update_labor(db, row, payload, current_user.company_id)


@router.delete("/labor/{labor_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_labor(
    work_order_id: str,
    labor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> None:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_labor(db, labor_id, work_order_id, current_user.company_id)
    labor.delete_labor(db, row)


# ---------------------------------------------------------------------------
# 额外成本（AdditionalCost）
# ---------------------------------------------------------------------------


def _ensure_cost(
    db: Session,
    cost_id: str,
    work_order_id: str,
    company_id: str,
) -> WorkOrderAdditionalCost:
    row = db.get(WorkOrderAdditionalCost, cost_id)
    if (
        row is None
        or row.work_order_id != work_order_id
        or row.company_id != company_id
    ):
        raise not_found("ADDITIONAL_COST_NOT_FOUND", "额外成本不存在")
    return row


@router.get("/additional-costs", response_model=list[AdditionalCostRead])
def list_additional_costs(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[WorkOrderAdditionalCost]:
    _ensure_wo(db, work_order_id, current_user.company_id)
    return addcost.list_additional_costs(db, work_order_id)


@router.post(
    "/additional-costs", response_model=AdditionalCostRead, status_code=status.HTTP_201_CREATED
)
def create_additional_cost(
    work_order_id: str,
    payload: AdditionalCostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderAdditionalCost:
    wo = _ensure_wo(db, work_order_id, current_user.company_id)
    return addcost.create_additional_cost(
        db, wo, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.patch("/additional-costs/{cost_id}", response_model=AdditionalCostRead)
def update_additional_cost(
    work_order_id: str,
    cost_id: str,
    payload: AdditionalCostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderAdditionalCost:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_cost(db, cost_id, work_order_id, current_user.company_id)
    return addcost.update_additional_cost(db, row, payload, current_user.company_id)


@router.delete(
    "/additional-costs/{cost_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_additional_cost(
    work_order_id: str,
    cost_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> None:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_cost(db, cost_id, work_order_id, current_user.company_id)
    addcost.delete_additional_cost(db, row)


# ---------------------------------------------------------------------------
# 总成本汇总（CostSummary）
# ---------------------------------------------------------------------------


@router.get("/cost-summary", response_model=CostSummaryRead)
def cost_summary(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> dict[str, Decimal]:
    _ensure_wo(db, work_order_id, current_user.company_id)
    return costsvc.cost_summary(db, work_order_id)
