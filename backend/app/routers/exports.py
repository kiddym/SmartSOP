"""实体级 CSV 导出（/api/v1/exports/{entity}）。

整表导出 5 类实体：work-orders、assets、locations、parts、meters。
每个端点用对应实体的 view 权限；数据走既有 list 服务（自带租户过滤）。
输出 UTF-8 + BOM，便于 Excel 正确识别中文；关联字段尽量解析成名称。
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.models.asset_category import AssetCategory
from app.models.location import Location
from app.models.maintenance_asset import Asset
from app.models.meter_category import MeterCategory
from app.models.part_category import PartCategory
from app.models.user import User
from app.models.work_order_category import WorkOrderCategory
from app.services import (
    location_service,
    maintenance_asset_service,
    meter_service,
    part_service,
    work_order_service,
)

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])

# BOM，让 Excel 按 UTF-8 解析中文表头/内容。
_BOM = "﻿"


def _name_map(db: Session, model: Any) -> dict[str, str]:
    """{id: name} 映射（仅活跃行）；用于把关联外键解析成可读名称。"""
    rows = db.execute(select(model.id, model.name).where(model.is_active.is_(True))).all()
    return {rid: name for rid, name in rows}


def _stream_csv(filename: str, header: list[str], rows: list[list[Any]]) -> StreamingResponse:
    """把表头+多行编成 CSV 流，带 BOM 与 attachment 头。"""

    def gen() -> Any:
        buf = io.StringIO()
        writer = csv.writer(buf)
        buf.write(_BOM)
        writer.writerow(header)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            writer.writerow(["" if c is None else c for c in row])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        gen(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/work-orders")
def export_work_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> StreamingResponse:
    assets = _name_map(db, Asset)
    cats = _name_map(db, WorkOrderCategory)
    users = {uid: name for uid, name in db.execute(select(User.id, User.name)).all()}
    header = ["custom_id", "title", "status", "priority", "due_date", "asset", "category", "assignee"]
    rows: list[list[Any]] = []
    for wo in work_order_service.list_work_orders(db):
        rows.append(
            [
                wo.custom_id,
                wo.title,
                wo.status.value,
                wo.priority.value,
                wo.due_date.isoformat() if wo.due_date else None,
                assets.get(wo.asset_id) if wo.asset_id else None,
                cats.get(wo.category_id) if wo.category_id else None,
                users.get(wo.primary_user_id) if wo.primary_user_id else None,
            ]
        )
    return _stream_csv("work-orders.csv", header, rows)


@router.get("/assets")
def export_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> StreamingResponse:
    cats = _name_map(db, AssetCategory)
    locs = _name_map(db, Location)
    header = [
        "custom_id",
        "name",
        "status",
        "category",
        "location",
        "manufacturer",
        "model",
        "serial_number",
    ]
    rows: list[list[Any]] = []
    for a in maintenance_asset_service.list_assets(db):
        rows.append(
            [
                a.custom_id,
                a.name,
                a.status.value,
                cats.get(a.category_id) if a.category_id else None,
                locs.get(a.location_id) if a.location_id else None,
                a.manufacturer,
                a.model,
                a.serial_number,
            ]
        )
    return _stream_csv("assets.csv", header, rows)


@router.get("/locations")
def export_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_VIEW)),
) -> StreamingResponse:
    locs = _name_map(db, Location)
    header = ["custom_id", "name", "address", "parent"]
    rows: list[list[Any]] = []
    for loc in location_service.list_locations(db):
        rows.append(
            [
                loc.custom_id,
                loc.name,
                loc.address,
                locs.get(loc.parent_id) if loc.parent_id else None,
            ]
        )
    return _stream_csv("locations.csv", header, rows)


@router.get("/parts")
def export_parts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_VIEW)),
) -> StreamingResponse:
    cats = _name_map(db, PartCategory)
    header = ["custom_id", "name", "quantity", "min_quantity", "unit", "cost", "category"]
    rows: list[list[Any]] = []
    for p in part_service.list_parts(db):
        rows.append(
            [
                p.custom_id,
                p.name,
                p.quantity,
                p.min_quantity,
                p.unit,
                p.cost,
                cats.get(p.category_id) if p.category_id else None,
            ]
        )
    return _stream_csv("parts.csv", header, rows)


@router.get("/meters")
def export_meters(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_VIEW)),
) -> StreamingResponse:
    assets = _name_map(db, Asset)
    locs = _name_map(db, Location)
    cats = _name_map(db, MeterCategory)
    header = ["custom_id", "name", "unit", "asset", "location", "category"]
    rows: list[list[Any]] = []
    for m in meter_service.list_meters(db):
        rows.append(
            [
                m.custom_id,
                m.name,
                m.unit,
                assets.get(m.asset_id) if m.asset_id else None,
                locs.get(m.location_id) if m.location_id else None,
                cats.get(m.meter_category_id) if m.meter_category_id else None,
            ]
        )
    return _stream_csv("meters.csv", header, rows)
