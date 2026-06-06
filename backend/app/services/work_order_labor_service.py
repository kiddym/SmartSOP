"""工单工时服务：费率解析、计时器（start/stop）、手填、CRUD。

成本计算（compute_cost）为纯函数，不依赖 now()；运行中行计 0。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict, not_found
from app.models.base import utcnow
from app.models.time_category import TimeCategory
from app.models.work_order import WorkOrder
from app.models.work_order_labor import WorkOrderLabor
from app.schemas.work_order_cost import LaborCreate, LaborTimerStart, LaborUpdate

_CENT = Decimal("0.01")


def is_running(row: WorkOrderLabor) -> bool:
    # 注意：schema 层 LaborRead.running 是同一谓词的平行实现（schema→service 循环依赖
    # 不能复用本函数），语义须与此保持同步。
    return row.started_at is not None and row.stopped_at is None


def compute_cost(row: WorkOrderLabor) -> Decimal:
    if is_running(row):
        return Decimal("0.00")
    raw = Decimal(row.duration_seconds) / Decimal(3600) * row.hourly_rate
    return raw.quantize(_CENT, rounding=ROUND_HALF_UP)


def _resolve_rate(
    db: Session,
    company_id: str,
    time_category_id: str | None,
    hourly_rate: Decimal | None,
) -> Decimal:
    cat: TimeCategory | None = None
    if time_category_id is not None:
        cat = db.get(TimeCategory, time_category_id)
        if cat is None or cat.company_id != company_id or not cat.is_active:
            raise not_found("TIME_CATEGORY_NOT_FOUND", "工时分类不存在")
    if hourly_rate is not None:
        return hourly_rate
    if cat is not None:
        return cat.hourly_rate
    return Decimal("0")


def list_labor(db: Session, work_order_id: str) -> list[WorkOrderLabor]:
    return list(
        db.execute(
            select(WorkOrderLabor)
            .where(WorkOrderLabor.work_order_id == work_order_id)
            .order_by(WorkOrderLabor.created_at, WorkOrderLabor.id)
        )
        .scalars()
        .all()
    )


def create_labor(
    db: Session,
    wo: WorkOrder,
    payload: LaborCreate,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderLabor:
    rate = _resolve_rate(db, company_id, payload.time_category_id, payload.hourly_rate)
    row = WorkOrderLabor(
        work_order_id=wo.id,
        user_id=payload.user_id if payload.user_id is not None else actor_user_id,
        time_category_id=payload.time_category_id,
        started_at=payload.started_at,
        stopped_at=payload.stopped_at,
        duration_seconds=payload.duration_seconds,
        hourly_rate=rate,
        notes=payload.notes,
        include_to_total=payload.include_to_total,
        company_id=company_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def start_timer(
    db: Session,
    wo: WorkOrder,
    payload: LaborTimerStart,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderLabor:
    uid = payload.user_id if payload.user_id is not None else actor_user_id
    # 注意：uid 为 None 时该检查无法拦截匿名计时器（路由层总会传 actor_user_id，
    # 生产环境不会出现 uid=None 的情况）。
    existing = db.execute(
        select(WorkOrderLabor).where(
            WorkOrderLabor.work_order_id == wo.id,
            WorkOrderLabor.user_id == uid,
            WorkOrderLabor.started_at.is_not(None),
            WorkOrderLabor.stopped_at.is_(None),
        )
    ).first()
    if existing is not None:
        raise conflict("LABOR_TIMER_RUNNING", "已有运行中的计时器")
    rate = _resolve_rate(db, company_id, payload.time_category_id, payload.hourly_rate)
    row = WorkOrderLabor(
        work_order_id=wo.id,
        user_id=uid,
        time_category_id=payload.time_category_id,
        started_at=utcnow(),
        stopped_at=None,
        duration_seconds=0,
        hourly_rate=rate,
        notes=payload.notes,
        company_id=company_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def stop_timer(db: Session, row: WorkOrderLabor) -> WorkOrderLabor:
    if row.started_at is None or row.stopped_at is not None:
        raise bad_request("LABOR_NOT_RUNNING", "该工时不是运行中的计时器")
    now = utcnow()
    row.duration_seconds = max(0, int((now - row.started_at).total_seconds()))
    row.stopped_at = now
    db.commit()
    db.refresh(row)
    return row


def update_labor(
    db: Session,
    row: WorkOrderLabor,
    payload: LaborUpdate,
    company_id: str,
) -> WorkOrderLabor:
    data = payload.model_dump(exclude_unset=True)
    # 校验 time_category_id 跨租户安全：若 patch 给了非 None 的新分类 id，
    # 必须确认该分类属于本租户且处于激活状态，否则拒绝以防悬挂/跨租户 FK。
    # 允许显式传 None（清除分类绑定，无需校验）。
    # 注意：不自动改价——通过校验后仍按原逻辑 setattr（保留 hourly_rate 快照，
    # 除非 patch 显式给了 hourly_rate）。
    if "time_category_id" in data and data["time_category_id"] is not None:
        cat = db.get(TimeCategory, data["time_category_id"])
        if cat is None or cat.company_id != company_id or not cat.is_active:
            raise not_found("TIME_CATEGORY_NOT_FOUND", "工时分类不存在")
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def delete_labor(db: Session, row: WorkOrderLabor) -> None:
    db.delete(row)
    db.commit()
