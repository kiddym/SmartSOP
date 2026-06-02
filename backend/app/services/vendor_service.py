"""供应商服务：CRUD（软删）、M:N 备件/资产/位置（全量替换，资产与位置写入校验同租户）、列表过滤（part_id 反查）。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.base import utcnow
from app.models.location import Location
from app.models.maintenance_asset import Asset
from app.models.vendor import Vendor, VendorAsset, VendorLocation, VendorPart
from app.schemas.partner import VendorCreate, VendorUpdate


def part_ids(db: Session, vendor_id: str) -> list[str]:
    return list(
        db.execute(
            select(VendorPart.part_id)
            .where(VendorPart.vendor_id == vendor_id)
            .order_by(VendorPart.part_id)
        )
        .scalars()
        .all()
    )


def asset_ids(db: Session, vendor_id: str) -> list[str]:
    return list(
        db.execute(
            select(VendorAsset.asset_id)
            .where(VendorAsset.vendor_id == vendor_id)
            .order_by(VendorAsset.asset_id)
        )
        .scalars()
        .all()
    )


def location_ids(db: Session, vendor_id: str) -> list[str]:
    return list(
        db.execute(
            select(VendorLocation.location_id)
            .where(VendorLocation.vendor_id == vendor_id)
            .order_by(VendorLocation.location_id)
        )
        .scalars()
        .all()
    )


def _set_parts(db: Session, vendor_id: str, company_id: str, part_id_list: list[str]) -> None:
    for pid in dict.fromkeys(part_id_list):
        db.add(VendorPart(vendor_id=vendor_id, part_id=pid, company_id=company_id))


def _validate_asset_ids(db: Session, ids: list[str], company_id: str) -> None:
    # 校验目标资产归属当前租户（不存在/非 active/他租户均 404）
    for aid in dict.fromkeys(ids):
        a = db.get(Asset, aid)
        if a is None or not a.is_active or a.company_id != company_id:
            raise not_found("ASSET_NOT_FOUND", "资产不存在")


def _validate_location_ids(db: Session, ids: list[str], company_id: str) -> None:
    # 校验目标位置归属当前租户（不存在/非 active/他租户均 404）
    for lid in dict.fromkeys(ids):
        loc = db.get(Location, lid)
        if loc is None or not loc.is_active or loc.company_id != company_id:
            raise not_found("LOCATION_NOT_FOUND", "位置不存在")


def _set_assets(db: Session, vendor_id: str, company_id: str, asset_id_list: list[str]) -> None:
    for aid in dict.fromkeys(asset_id_list):
        db.add(VendorAsset(vendor_id=vendor_id, asset_id=aid, company_id=company_id))


def _set_locations(db: Session, vendor_id: str, company_id: str, loc_id_list: list[str]) -> None:
    for lid in dict.fromkeys(loc_id_list):
        db.add(VendorLocation(vendor_id=vendor_id, location_id=lid, company_id=company_id))


def create_vendor(
    db: Session, payload: VendorCreate, company_id: str, actor_user_id: str | None
) -> Vendor:
    v = Vendor(
        name=payload.name,
        vendor_type=payload.vendor_type,
        description=payload.description,
        rate=payload.rate,
        address=payload.address,
        phone=payload.phone,
        email=payload.email,
        website=payload.website,
        company_id=company_id,
    )
    # 写关联前校验新关联目标归属当前租户
    _validate_asset_ids(db, payload.asset_ids, company_id)
    _validate_location_ids(db, payload.location_ids, company_id)
    db.add(v)
    db.flush()
    _set_parts(db, v.id, company_id, payload.part_ids)
    _set_assets(db, v.id, company_id, payload.asset_ids)
    _set_locations(db, v.id, company_id, payload.location_ids)
    db.commit()
    db.refresh(v)
    return v


def list_vendors(db: Session, *, part_id: str | None = None) -> list[Vendor]:
    stmt = select(Vendor).where(Vendor.is_active.is_(True))
    if part_id is not None:
        stmt = stmt.where(
            Vendor.id.in_(select(VendorPart.vendor_id).where(VendorPart.part_id == part_id))
        )
    return list(db.execute(stmt.order_by(Vendor.name, Vendor.id)).scalars().all())


def get_vendor(db: Session, vendor_id: str) -> Vendor | None:
    v = db.get(Vendor, vendor_id)
    if v is None or not v.is_active:
        return None
    return v


def update_vendor(
    db: Session, v: Vendor, payload: VendorUpdate, company_id: str, actor_user_id: str | None
) -> Vendor:
    data = payload.model_dump(exclude_unset=True)
    new_parts = data.pop("part_ids", None)
    new_assets = data.pop("asset_ids", None)
    new_locations = data.pop("location_ids", None)
    # 校验须在 setattr 之前，确保非法目标不会落库
    if new_assets is not None:
        _validate_asset_ids(db, new_assets, company_id)
    if new_locations is not None:
        _validate_location_ids(db, new_locations, company_id)
    for k, val in data.items():
        setattr(v, k, val)
    if new_parts is not None:
        db.execute(delete(VendorPart).where(VendorPart.vendor_id == v.id))
        _set_parts(db, v.id, company_id, new_parts)
    if new_assets is not None:
        db.execute(delete(VendorAsset).where(VendorAsset.vendor_id == v.id))
        _set_assets(db, v.id, company_id, new_assets)
    if new_locations is not None:
        db.execute(delete(VendorLocation).where(VendorLocation.vendor_id == v.id))
        _set_locations(db, v.id, company_id, new_locations)
    db.commit()
    db.refresh(v)
    return v


def delete_vendor(db: Session, v: Vendor) -> None:
    v.is_active = False
    v.deleted_at = utcnow()
    db.commit()
