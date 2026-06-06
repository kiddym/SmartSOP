"""位置平面图服务：按位置列出 / 新建 / 部分更新（PATCH 语义）/ 硬删。

平面图与位置 1:N，随位置 CASCADE 删除。子资源不软删（硬删），与既有
1:N 子资源（如备件消耗台账）风格一致。请求内单次 commit。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.floor_plan import FloorPlan
from app.schemas.floor_plan import FloorPlanCreate, FloorPlanUpdate


def list_by_location(db: Session, location_id: str) -> list[FloorPlan]:
    return list(
        db.execute(
            select(FloorPlan)
            .where(FloorPlan.location_id == location_id)
            .order_by(FloorPlan.created_at, FloorPlan.id)
        )
        .scalars()
        .all()
    )


def get(db: Session, floor_plan_id: str) -> FloorPlan | None:
    return db.execute(
        select(FloorPlan).where(FloorPlan.id == floor_plan_id)
    ).scalar_one_or_none()


def create(
    db: Session, location_id: str, company_id: str, payload: FloorPlanCreate
) -> FloorPlan:
    row = FloorPlan(
        location_id=location_id,
        company_id=company_id,
        name=payload.name,
        image_url=payload.image_url,
        area=payload.area,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update(db: Session, row: FloorPlan, payload: FloorPlanUpdate) -> FloorPlan:
    """PATCH 语义：仅覆盖载荷中显式给出的字段。"""
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, row: FloorPlan) -> None:
    db.delete(row)
    db.commit()
