"""实体级 CSV 批量导入与模板下载（/api/v1/imports/{entity}）。

支持 assets / locations / parts / meters 四类核心主数据：
- GET /{entity}/template：下载导入模板 CSV（表头 + 1 行示例），UTF-8 + BOM + attachment。
- POST /{entity}：上传 CSV 文件逐行创建实体；逐行容错（单行失败记错误不中断整批）。

关联字段（category/location/parent/asset）按**名称**在当前租户内解析为 id；
解析不到（或同名多条歧义）时该行记错误。租户隔离：company_id 取自当前用户。

注意：各 create 服务内部自带 db.commit()，故成功行立即落库；失败行在
commit 之前抛错，捕获后 db.rollback() 清理半成品，保证一行失败不污染整批。

权限随实体不同（ASSET_CREATE / LOCATION_CREATE / PART_CREATE / METER_CREATE），
因路径参数动态，故在 handler 内手工校验而非装饰器级 Depends。
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_current_user, get_db, user_permission_codes
from app.errors import bad_request, forbidden
from app.models.asset_category import AssetCategory
from app.models.asset_status import AssetStatus
from app.models.location import Location
from app.models.maintenance_asset import Asset
from app.models.meter_category import MeterCategory
from app.models.part_category import PartCategory
from app.models.user import User
from app.schemas.asset import AssetCreate
from app.schemas.location import LocationCreate
from app.schemas.meter import MeterCreate
from app.schemas.part import PartCreate
from app.services import (
    location_service,
    maintenance_asset_service,
    meter_service,
    part_service,
)

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

# BOM，让 Excel 按 UTF-8 解析中文表头/示例。
_BOM = "﻿"


class _RowError(Exception):
    """单行解析/创建错误；message 用于汇总返回。"""


def _resolve_name(db: Session, model: Any, name: str, company_id: str, label: str) -> str:
    """把关联实体名称解析为 id（当前租户、活跃）。不存在/歧义 → _RowError。"""
    rows = (
        db.execute(
            select(model.id).where(
                model.name == name,
                model.company_id == company_id,
                model.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise _RowError(f"{label}“{name}”不存在")
    if len(rows) > 1:
        raise _RowError(f"{label}“{name}”有多条同名记录，无法唯一匹配")
    return str(rows[0])


def _decimal(value: str, label: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise _RowError(f"{label}“{value}”不是合法数值") from exc


# --- 每类实体：行 → 创建 ---


def _build_asset(db: Session, row: dict[str, str], company_id: str, _user_id: str) -> None:
    name = row.get("name", "").strip()
    if not name:
        raise _RowError("name 为必填")
    category = row.get("category", "").strip()
    location = row.get("location", "").strip()
    status_raw = row.get("status", "").strip() or "OPERATIONAL"
    try:
        status = AssetStatus(status_raw)
    except ValueError as exc:
        raise _RowError(f"status“{status_raw}”不是合法状态") from exc
    payload = AssetCreate(
        name=name,
        status=status,
        manufacturer=row.get("manufacturer", "").strip(),
        model=row.get("model", "").strip(),
        serial_number=row.get("serial_number", "").strip(),
        category_id=(
            _resolve_name(db, AssetCategory, category, company_id, "资产分类") if category else None
        ),
        location_id=(
            _resolve_name(db, Location, location, company_id, "位置") if location else None
        ),
    )
    maintenance_asset_service.create_asset(db, payload, company_id)


def _build_location(db: Session, row: dict[str, str], company_id: str, _user_id: str) -> None:
    name = row.get("name", "").strip()
    if not name:
        raise _RowError("name 为必填")
    parent = row.get("parent", "").strip()
    payload = LocationCreate(
        name=name,
        address=row.get("address", "").strip(),
        parent_id=(_resolve_name(db, Location, parent, company_id, "父位置") if parent else None),
    )
    location_service.create_location(db, payload, company_id)


def _build_part(db: Session, row: dict[str, str], company_id: str, user_id: str) -> None:
    name = row.get("name", "").strip()
    if not name:
        raise _RowError("name 为必填")
    category = row.get("category", "").strip()
    payload = PartCreate(
        name=name,
        description=row.get("description", "").strip(),
        unit=row.get("unit", "").strip(),
        cost=_decimal(row["cost"], "cost") if row.get("cost", "").strip() else Decimal("0"),
        quantity=(
            _decimal(row["quantity"], "quantity")
            if row.get("quantity", "").strip()
            else Decimal("0")
        ),
        min_quantity=(
            _decimal(row["min_quantity"], "min_quantity")
            if row.get("min_quantity", "").strip()
            else Decimal("0")
        ),
        category_id=(
            _resolve_name(db, PartCategory, category, company_id, "备件分类") if category else None
        ),
    )
    part_service.create_part(db, payload, company_id, actor_user_id=user_id)


def _build_meter(db: Session, row: dict[str, str], company_id: str, user_id: str) -> None:
    name = row.get("name", "").strip()
    if not name:
        raise _RowError("name 为必填")
    unit = row.get("unit", "").strip()
    if not unit:
        raise _RowError("unit 为必填")
    asset = row.get("asset", "").strip()
    location = row.get("location", "").strip()
    category = row.get("category", "").strip()
    payload = MeterCreate(
        name=name,
        unit=unit,
        asset_id=(_resolve_name(db, Asset, asset, company_id, "资产") if asset else None),
        location_id=(
            _resolve_name(db, Location, location, company_id, "位置") if location else None
        ),
        meter_category_id=(
            _resolve_name(db, MeterCategory, category, company_id, "计量分类") if category else None
        ),
    )
    meter_service.create_meter(db, payload, company_id, actor_user_id=user_id)


# entity -> (表头, 示例行, 创建权限, 行处理器(db, row, company_id, user_id))
_Builder = Callable[[Session, dict[str, str], str, str], None]

_SPECS: dict[str, tuple[list[str], list[str], str, _Builder]] = {
    "assets": (
        ["name", "status", "category", "location", "manufacturer", "model", "serial_number"],
        ["示例泵", "OPERATIONAL", "", "", "ACME", "X1", "SN-001"],
        permissions.ASSET_CREATE,
        _build_asset,
    ),
    "locations": (
        ["name", "address", "parent"],
        ["示例厂区", "示例路 1 号", ""],
        permissions.LOCATION_CREATE,
        _build_location,
    ),
    "parts": (
        ["name", "description", "unit", "cost", "quantity", "min_quantity", "category"],
        ["示例滤芯", "高效滤芯", "个", "12.5", "10", "2", ""],
        permissions.PART_CREATE,
        _build_part,
    ),
    "meters": (
        ["name", "unit", "asset", "location", "category"],
        ["示例温度表", "℃", "", "", ""],
        permissions.METER_CREATE,
        _build_meter,
    ),
}


def _spec_or_404(entity: str) -> tuple[list[str], list[str], str, _Builder]:
    spec = _SPECS.get(entity)
    if spec is None:
        raise bad_request("IMPORT_ENTITY_UNSUPPORTED", "不支持导入该实体")
    return spec


@router.get("/{entity}/template")
def download_template(
    entity: str,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    # 模板仅含表头/示例（无敏感数据），认证即可下载；导入权限在 POST 校验。
    header, sample, _perm, _builder = _spec_or_404(entity)
    buf = io.StringIO()
    buf.write(_BOM)
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerow(sample)
    data = buf.getvalue()

    def gen() -> Any:
        yield data

    return StreamingResponse(
        gen(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={entity}-template.csv"},
    )


@router.post("/{entity}")
async def import_csv(
    entity: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _header, _sample, perm, builder = _spec_or_404(entity)
    if perm not in user_permission_codes(db, current_user):
        raise forbidden("FORBIDDEN", "权限不足")
    company_id = current_user.company_id

    raw = await file.read()
    text = raw.decode("utf-8-sig")  # 兼容 Excel 写出的 BOM。
    reader = csv.DictReader(io.StringIO(text))

    created = 0
    failed = 0
    errors: list[dict[str, Any]] = []

    # 行号从 2 起（1 为表头），与用户在表格里看到的一致。
    for idx, row in enumerate(reader, start=2):
        clean = {k.strip(): (v if v is not None else "") for k, v in row.items() if k is not None}
        try:
            builder(db, clean, company_id, current_user.id)
            created += 1
        except _RowError as exc:
            db.rollback()
            failed += 1
            errors.append({"row": idx, "message": str(exc)})
        except Exception as exc:  # 逐行容错：任何创建错误都不中断整批
            db.rollback()
            failed += 1
            # 业务错误 detail 形如 {"code","message"}；取 message，否则回退到字符串化。
            detail = getattr(exc, "detail", None)
            if isinstance(detail, dict):
                msg = str(detail.get("message") or detail.get("code") or exc)
            elif isinstance(detail, str):
                msg = detail
            else:
                msg = str(exc) or exc.__class__.__name__
            errors.append({"row": idx, "message": msg})

    return {"created": created, "failed": failed, "errors": errors}
