"""CMMS 资产服务：CRUD、树（防环）、customId、barcode/nfc 唯一与查询、关联、停机。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app.errors import bad_request, conflict, not_found
from app.models.asset_downtime import AssetDowntime
from app.models.asset_status import DOWN_STATUSES, AssetStatus
from app.models.base import utcnow
from app.models.customer import Customer, CustomerAsset
from app.models.maintenance_asset import Asset, AssetTeam, AssetUser
from app.models.part import Part, PartAsset
from app.models.vendor import Vendor, VendorAsset
from app.schemas.asset import AssetCreate, AssetUpdate, DowntimeClose, DowntimeCreate
from app.services import custom_field_service, sequence_service


def assigned_user_ids(db: Session, asset_id: str) -> list[str]:
    return list(
        db.execute(select(AssetUser.user_id).where(AssetUser.asset_id == asset_id)).scalars().all()
    )


def team_ids(db: Session, asset_id: str) -> list[str]:
    return list(
        db.execute(select(AssetTeam.team_id).where(AssetTeam.asset_id == asset_id)).scalars().all()
    )


def vendor_ids(db: Session, asset_id: str) -> list[str]:
    return list(
        db.execute(
            select(VendorAsset.vendor_id)
            .where(VendorAsset.asset_id == asset_id)
            .order_by(VendorAsset.vendor_id)
        )
        .scalars()
        .all()
    )


def customer_ids(db: Session, asset_id: str) -> list[str]:
    return list(
        db.execute(
            select(CustomerAsset.customer_id)
            .where(CustomerAsset.asset_id == asset_id)
            .order_by(CustomerAsset.customer_id)
        )
        .scalars()
        .all()
    )


def part_ids(db: Session, asset_id: str) -> list[str]:
    return list(
        db.execute(
            select(PartAsset.part_id)
            .where(PartAsset.asset_id == asset_id)
            .order_by(PartAsset.part_id)
        )
        .scalars()
        .all()
    )


def to_read(db: Session, a: Asset) -> dict[str, object]:
    return {
        "id": a.id,
        "custom_id": a.custom_id,
        "name": a.name,
        "description": a.description,
        "parent_id": a.parent_id,
        "location_id": a.location_id,
        "category_id": a.category_id,
        "status": a.status,
        "serial_number": a.serial_number,
        "model": a.model,
        "manufacturer": a.manufacturer,
        "power": a.power,
        "warranty_expiration_date": a.warranty_expiration_date,
        "in_service_date": a.in_service_date,
        "acquisition_cost": a.acquisition_cost,
        "barcode": a.barcode,
        "nfc_id": a.nfc_id,
        "primary_user_id": a.primary_user_id,
        "area": a.area,
        "additional_infos": a.additional_infos,
        "image_url": a.image_url,
        "assigned_user_ids": assigned_user_ids(db, a.id),
        "team_ids": team_ids(db, a.id),
        "vendor_ids": vendor_ids(db, a.id),
        "customer_ids": customer_ids(db, a.id),
        "part_ids": part_ids(db, a.id),
        "custom_values": a.custom_values or {},
    }


def _check_code_unique(
    db: Session,
    field: InstrumentedAttribute[str | None],
    value: str | None,
    exclude_id: str | None,
) -> None:
    """barcode / nfc_id 在当前租户内（read-scope 已限定）唯一。value 为空跳过。"""
    if not value:
        return
    stmt = select(Asset.id).where(field == value, Asset.is_active.is_(True))
    if exclude_id is not None:
        stmt = stmt.where(Asset.id != exclude_id)
    if db.execute(stmt).first() is not None:
        label = "条码" if field is Asset.barcode else "NFC 标识"
        raise conflict("ASSET_CODE_TAKEN", f"{label}已被占用")


def _descendant_ids(db: Session, asset_id: str) -> set[str]:
    out: set[str] = set()
    frontier = [asset_id]
    while frontier:
        rows = (
            db.execute(
                select(Asset.id).where(Asset.parent_id.in_(frontier), Asset.is_active.is_(True))
            )
            .scalars()
            .all()
        )
        rows = [r for r in rows if r not in out]
        out.update(rows)
        frontier = rows
    return out


def _validate_parent(db: Session, asset_id: str, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if parent_id == asset_id:
        raise bad_request("ASSET_CYCLE", "父资产不能是自身")
    if parent_id in _descendant_ids(db, asset_id):
        raise bad_request("ASSET_CYCLE", "父资产不能是自身的后代")


def _validate_owned(
    db: Session, model: type, ids: list[str], company_id: str, code: str, label: str
) -> None:
    """校验目标实体归属当前租户（不存在/非 active/他租户均 404）。"""
    for eid in dict.fromkeys(ids):
        row = db.get(model, eid)
        if row is None or not row.is_active or row.company_id != company_id:
            raise not_found(code, f"{label}不存在")


def _sync_relations(
    db: Session,
    a: Asset,
    user_ids: list[str] | None,
    team_ids_: list[str] | None,
    vendor_ids_: list[str] | None,
    customer_ids_: list[str] | None,
    part_ids_: list[str] | None,
    company_id: str,
) -> None:
    if user_ids is not None:
        db.execute(delete(AssetUser).where(AssetUser.asset_id == a.id))
        for uid in dict.fromkeys(user_ids):
            db.add(AssetUser(asset_id=a.id, user_id=uid, company_id=company_id))
    if team_ids_ is not None:
        db.execute(delete(AssetTeam).where(AssetTeam.asset_id == a.id))
        for tid in dict.fromkeys(team_ids_):
            db.add(AssetTeam(asset_id=a.id, team_id=tid, company_id=company_id))
    if vendor_ids_ is not None:
        db.execute(delete(VendorAsset).where(VendorAsset.asset_id == a.id))
        for vid in dict.fromkeys(vendor_ids_):
            db.add(VendorAsset(asset_id=a.id, vendor_id=vid, company_id=company_id))
    if customer_ids_ is not None:
        db.execute(delete(CustomerAsset).where(CustomerAsset.asset_id == a.id))
        for cid in dict.fromkeys(customer_ids_):
            db.add(CustomerAsset(asset_id=a.id, customer_id=cid, company_id=company_id))
    if part_ids_ is not None:
        db.execute(delete(PartAsset).where(PartAsset.asset_id == a.id))
        for pid in dict.fromkeys(part_ids_):
            db.add(PartAsset(asset_id=a.id, part_id=pid, company_id=company_id))


def _validate_partner_ids(
    db: Session,
    vendor_ids_: list[str] | None,
    customer_ids_: list[str] | None,
    part_ids_: list[str] | None,
    company_id: str,
) -> None:
    if vendor_ids_ is not None:
        _validate_owned(db, Vendor, vendor_ids_, company_id, "VENDOR_NOT_FOUND", "供应商")
    if customer_ids_ is not None:
        _validate_owned(db, Customer, customer_ids_, company_id, "CUSTOMER_NOT_FOUND", "客户")
    if part_ids_ is not None:
        _validate_owned(db, Part, part_ids_, company_id, "PART_NOT_FOUND", "备件")


def create_asset(db: Session, payload: AssetCreate, company_id: str) -> Asset:
    custom_field_service.validate_values(db, "asset", payload.custom_values)
    _check_code_unique(db, Asset.barcode, payload.barcode, None)
    _check_code_unique(db, Asset.nfc_id, payload.nfc_id, None)
    _validate_partner_ids(
        db, payload.vendor_ids, payload.customer_ids, payload.part_ids, company_id
    )
    seq = sequence_service.next_value(db, "asset", company_id)
    data = payload.model_dump(
        exclude={
            "assigned_user_ids",
            "team_ids",
            "vendor_ids",
            "customer_ids",
            "part_ids",
        }
    )
    a = Asset(custom_id=sequence_service.format_custom_id("A", seq), company_id=company_id, **data)
    db.add(a)
    db.flush()
    _sync_relations(
        db,
        a,
        payload.assigned_user_ids,
        payload.team_ids,
        payload.vendor_ids,
        payload.customer_ids,
        payload.part_ids,
        company_id,
    )
    db.commit()
    db.refresh(a)
    return a


def list_assets(
    db: Session,
    *,
    location_id: str | None = None,
    category_id: str | None = None,
    status: str | None = None,
    parent_id: str | None = None,
) -> list[Asset]:
    stmt = select(Asset).where(Asset.is_active.is_(True))
    if location_id is not None:
        stmt = stmt.where(Asset.location_id == location_id)
    if category_id is not None:
        stmt = stmt.where(Asset.category_id == category_id)
    if status is not None:
        stmt = stmt.where(Asset.status == status)
    if parent_id is not None:
        stmt = stmt.where(Asset.parent_id == parent_id)
    return list(db.execute(stmt).scalars().all())


def list_children(db: Session, asset_id: str) -> list[Asset]:
    return list(
        db.execute(select(Asset).where(Asset.parent_id == asset_id, Asset.is_active.is_(True)))
        .scalars()
        .all()
    )


def get_asset(db: Session, asset_id: str) -> Asset | None:
    a = db.get(Asset, asset_id)
    if a is None or not a.is_active:
        return None
    return a


def get_by_barcode(db: Session, code: str) -> Asset | None:
    return db.execute(
        select(Asset).where(Asset.barcode == code, Asset.is_active.is_(True))
    ).scalar_one_or_none()


def get_by_nfc(db: Session, nfc: str) -> Asset | None:
    return db.execute(
        select(Asset).where(Asset.nfc_id == nfc, Asset.is_active.is_(True))
    ).scalar_one_or_none()


def update_asset(db: Session, a: Asset, payload: AssetUpdate, company_id: str) -> Asset:
    data = payload.model_dump(exclude_unset=True)
    # custom_values 不能走通用 setattr 循环（会整体覆盖且绕过校验），单独处理
    custom_values = data.pop("custom_values", None)
    if "parent_id" in data:
        _validate_parent(db, a.id, data["parent_id"])
    if "barcode" in data:
        _check_code_unique(db, Asset.barcode, data["barcode"], a.id)
    if "nfc_id" in data:
        _check_code_unique(db, Asset.nfc_id, data["nfc_id"], a.id)
    user_ids = data.pop("assigned_user_ids", None)
    team_ids_ = data.pop("team_ids", None)
    vendor_ids_ = data.pop("vendor_ids", None)
    customer_ids_ = data.pop("customer_ids", None)
    part_ids_ = data.pop("part_ids", None)
    # 校验须在 setattr 之前，确保非法目标不会落库
    _validate_partner_ids(db, vendor_ids_, customer_ids_, part_ids_, company_id)
    old_status = a.status
    for k, v in data.items():
        setattr(a, k, v)
    if "status" in data:
        apply_status_transition(db, a, old_status, a.status, company_id)
    if custom_values is not None:
        custom_field_service.validate_values(db, "asset", custom_values)
        a.custom_values = {**(a.custom_values or {}), **custom_values}
    _sync_relations(db, a, user_ids, team_ids_, vendor_ids_, customer_ids_, part_ids_, company_id)
    db.commit()
    db.refresh(a)
    return a


def delete_asset(db: Session, a: Asset) -> None:
    if list_children(db, a.id):
        raise bad_request("ASSET_HAS_CHILDREN", "请先删除子资产")
    a.is_active = False
    a.deleted_at = utcnow()
    db.commit()


def _open_downtimes_for(db: Session, asset_id: str) -> list[AssetDowntime]:
    return list(
        db.execute(
            select(AssetDowntime).where(
                AssetDowntime.asset_id == asset_id, AssetDowntime.ended_at.is_(None)
            )
        )
        .scalars()
        .all()
    )


def _go_down(db: Session, asset: Asset, company_id: str) -> None:
    now = utcnow()
    db.add(
        AssetDowntime(
            asset_id=asset.id,
            downtime_type="auto",
            source_asset_id=None,
            started_at=now,
            company_id=company_id,
        )
    )
    # 向下级联：遍历全部 active 后代，UP 的置 DOWN 并记 prior，已 DOWN 的仅记依赖。
    for did in _descendant_ids(db, asset.id):
        d = db.get(Asset, did)
        if d is None or not d.is_active:
            continue
        if d.status in DOWN_STATUSES:
            db.add(
                AssetDowntime(
                    asset_id=d.id,
                    downtime_type="cascade",
                    source_asset_id=asset.id,
                    prior_status=None,
                    started_at=now,
                    company_id=company_id,
                )
            )
        else:
            prior = d.status.value
            d.status = AssetStatus.DOWN
            db.add(
                AssetDowntime(
                    asset_id=d.id,
                    downtime_type="cascade",
                    source_asset_id=asset.id,
                    prior_status=prior,
                    started_at=now,
                    company_id=company_id,
                )
            )


def _recover(db: Session, asset: Asset, company_id: str) -> None:
    now = utcnow()
    for dt in _open_downtimes_for(db, asset.id):
        if dt.source_asset_id is None and dt.downtime_type == "auto":
            dt.ended_at = now
    # 级联反转：关闭所有 source=本资产的 open cascade，再按 prior_status 还原后代状态。
    cascade_rows = list(
        db.execute(
            select(AssetDowntime)
            .where(AssetDowntime.source_asset_id == asset.id, AssetDowntime.ended_at.is_(None))
            .order_by(AssetDowntime.started_at)
        )
        .scalars()
        .all()
    )
    affected: dict[str, str | None] = {}
    for dt in cascade_rows:
        dt.ended_at = now
        # 按 started_at 升序遍历，取每个后代最早一条非空 prior_status
        if dt.asset_id not in affected or (
            affected[dt.asset_id] is None and dt.prior_status is not None
        ):
            affected[dt.asset_id] = dt.prior_status
    db.flush()  # 让 ended_at 对随后的 open 复查可见
    for did, prior in affected.items():
        d = db.get(Asset, did)
        if d is None or not d.is_active:
            continue
        if _open_downtimes_for(db, did):
            continue  # 仍有独立 open 停机 -> 维持 DOWN
        d.status = AssetStatus(prior) if prior is not None else AssetStatus.OPERATIONAL


def apply_status_transition(
    db: Session, asset: Asset, old_status: AssetStatus, new_status: AssetStatus, company_id: str
) -> None:
    was_down = old_status in DOWN_STATUSES
    now_down = new_status in DOWN_STATUSES
    if not was_down and now_down:
        _go_down(db, asset, company_id)
    elif was_down and not now_down:
        _recover(db, asset, company_id)
    # UP->UP / DOWN->DOWN：无副作用


# --- 停机 ---


def add_downtime(
    db: Session, asset_id: str, payload: DowntimeCreate, company_id: str
) -> AssetDowntime:
    dt = AssetDowntime(
        asset_id=asset_id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        reason=payload.reason,
        downtime_type=payload.downtime_type,
        company_id=company_id,
    )
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return dt


def list_downtimes(db: Session, asset_id: str) -> list[AssetDowntime]:
    return list(
        db.execute(
            select(AssetDowntime)
            .where(AssetDowntime.asset_id == asset_id)
            .order_by(AssetDowntime.started_at)
        )
        .scalars()
        .all()
    )


def get_downtime(db: Session, downtime_id: str) -> AssetDowntime | None:
    return db.get(AssetDowntime, downtime_id)


def close_downtime(db: Session, dt: AssetDowntime, payload: DowntimeClose) -> AssetDowntime:
    dt.ended_at = payload.ended_at
    db.commit()
    db.refresh(dt)
    return dt
