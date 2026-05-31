"""供应商服务：CRUD（软删）、M:N 备件（全量替换）、列表过滤（part_id 反查）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.vendor import Vendor, VendorPart
from app.schemas.partner import VendorCreate, VendorUpdate


def part_ids(db: Session, vendor_id: str) -> list[str]:
    return list(db.execute(
        select(VendorPart.part_id).where(VendorPart.vendor_id == vendor_id)
        .order_by(VendorPart.part_id)).scalars().all())


def _set_parts(db: Session, vendor_id: str, company_id: str,
               part_id_list: list[str]) -> None:
    for pid in dict.fromkeys(part_id_list):
        db.add(VendorPart(vendor_id=vendor_id, part_id=pid, company_id=company_id))


def create_vendor(db: Session, payload: VendorCreate, company_id: str,
                  actor_user_id: str | None) -> Vendor:
    v = Vendor(
        name=payload.name, vendor_type=payload.vendor_type,
        description=payload.description, rate=payload.rate, address=payload.address,
        phone=payload.phone, email=payload.email, website=payload.website,
        company_id=company_id,
    )
    db.add(v)
    db.flush()
    _set_parts(db, v.id, company_id, payload.part_ids)
    db.commit()
    db.refresh(v)
    return v


def list_vendors(db: Session, *, part_id: str | None = None) -> list[Vendor]:
    stmt = select(Vendor).where(Vendor.is_active.is_(True))
    if part_id is not None:
        stmt = stmt.where(Vendor.id.in_(
            select(VendorPart.vendor_id).where(VendorPart.part_id == part_id)))
    return list(db.execute(stmt.order_by(Vendor.name, Vendor.id)).scalars().all())


def get_vendor(db: Session, vendor_id: str) -> Vendor | None:
    v = db.get(Vendor, vendor_id)
    if v is None or not v.is_active:
        return None
    return v


def update_vendor(db: Session, v: Vendor, payload: VendorUpdate, company_id: str,
                  actor_user_id: str | None) -> Vendor:
    data = payload.model_dump(exclude_unset=True)
    new_parts = data.pop("part_ids", None)
    for k, val in data.items():
        setattr(v, k, val)
    if new_parts is not None:
        db.execute(VendorPart.__table__.delete().where(VendorPart.vendor_id == v.id))
        _set_parts(db, v.id, company_id, new_parts)
    db.commit()
    db.refresh(v)
    return v


def delete_vendor(db: Session, v: Vendor) -> None:
    v.is_active = False
    v.deleted_at = utcnow()
    db.commit()
