"""客户服务：CRUD（软删）、M:N 备件/资产/位置（全量替换，资产与位置写入校验同租户）、列表过滤（part_id 反查）。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.base import utcnow
from app.models.customer import Customer, CustomerAsset, CustomerLocation, CustomerPart
from app.models.location import Location
from app.models.maintenance_asset import Asset
from app.schemas.partner import CustomerCreate, CustomerUpdate


def part_ids(db: Session, customer_id: str) -> list[str]:
    return list(
        db.execute(
            select(CustomerPart.part_id)
            .where(CustomerPart.customer_id == customer_id)
            .order_by(CustomerPart.part_id)
        )
        .scalars()
        .all()
    )


def asset_ids(db: Session, customer_id: str) -> list[str]:
    return list(
        db.execute(
            select(CustomerAsset.asset_id)
            .where(CustomerAsset.customer_id == customer_id)
            .order_by(CustomerAsset.asset_id)
        )
        .scalars()
        .all()
    )


def location_ids(db: Session, customer_id: str) -> list[str]:
    return list(
        db.execute(
            select(CustomerLocation.location_id)
            .where(CustomerLocation.customer_id == customer_id)
            .order_by(CustomerLocation.location_id)
        )
        .scalars()
        .all()
    )


def _set_parts(db: Session, customer_id: str, company_id: str, part_id_list: list[str]) -> None:
    for pid in dict.fromkeys(part_id_list):
        db.add(CustomerPart(customer_id=customer_id, part_id=pid, company_id=company_id))


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


def _set_assets(db: Session, customer_id: str, company_id: str, asset_id_list: list[str]) -> None:
    for aid in dict.fromkeys(asset_id_list):
        db.add(CustomerAsset(customer_id=customer_id, asset_id=aid, company_id=company_id))


def _set_locations(db: Session, customer_id: str, company_id: str, loc_id_list: list[str]) -> None:
    for lid in dict.fromkeys(loc_id_list):
        db.add(CustomerLocation(customer_id=customer_id, location_id=lid, company_id=company_id))


def create_customer(
    db: Session, payload: CustomerCreate, company_id: str, actor_user_id: str | None
) -> Customer:
    c = Customer(
        name=payload.name,
        customer_type=payload.customer_type,
        description=payload.description,
        rate=payload.rate,
        billing_currency=payload.billing_currency,
        billing_name=payload.billing_name,
        billing_address=payload.billing_address,
        billing_address2=payload.billing_address2,
        address=payload.address,
        phone=payload.phone,
        email=payload.email,
        website=payload.website,
        company_id=company_id,
    )
    # 写关联前校验新关联目标归属当前租户
    _validate_asset_ids(db, payload.asset_ids, company_id)
    _validate_location_ids(db, payload.location_ids, company_id)
    db.add(c)
    db.flush()
    _set_parts(db, c.id, company_id, payload.part_ids)
    _set_assets(db, c.id, company_id, payload.asset_ids)
    _set_locations(db, c.id, company_id, payload.location_ids)
    db.commit()
    db.refresh(c)
    return c


def list_customers(db: Session, *, part_id: str | None = None) -> list[Customer]:
    stmt = select(Customer).where(Customer.is_active.is_(True))
    if part_id is not None:
        stmt = stmt.where(
            Customer.id.in_(select(CustomerPart.customer_id).where(CustomerPart.part_id == part_id))
        )
    return list(db.execute(stmt.order_by(Customer.name, Customer.id)).scalars().all())


def get_customer(db: Session, customer_id: str) -> Customer | None:
    c = db.get(Customer, customer_id)
    if c is None or not c.is_active:
        return None
    return c


def update_customer(
    db: Session, c: Customer, payload: CustomerUpdate, company_id: str, actor_user_id: str | None
) -> Customer:
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
        setattr(c, k, val)
    if new_parts is not None:
        db.execute(delete(CustomerPart).where(CustomerPart.customer_id == c.id))
        _set_parts(db, c.id, company_id, new_parts)
    if new_assets is not None:
        db.execute(delete(CustomerAsset).where(CustomerAsset.customer_id == c.id))
        _set_assets(db, c.id, company_id, new_assets)
    if new_locations is not None:
        db.execute(delete(CustomerLocation).where(CustomerLocation.customer_id == c.id))
        _set_locations(db, c.id, company_id, new_locations)
    db.commit()
    db.refresh(c)
    return c


def delete_customer(db: Session, c: Customer) -> None:
    c.is_active = False
    c.deleted_at = utcnow()
    db.commit()
