"""CMMS 资产服务：CRUD、树（防环）、customId、barcode/nfc 唯一与查询、关联、停机。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict
from app.models.asset_downtime import AssetDowntime
from app.models.base import utcnow
from app.models.maintenance_asset import Asset, AssetTeam, AssetUser
from app.schemas.asset import AssetCreate, AssetUpdate, DowntimeClose, DowntimeCreate
from app.services import sequence_service


def assigned_user_ids(db: Session, asset_id: str) -> list[str]:
    return list(
        db.execute(select(AssetUser.user_id).where(AssetUser.asset_id == asset_id)).scalars().all()
    )


def team_ids(db: Session, asset_id: str) -> list[str]:
    return list(
        db.execute(select(AssetTeam.team_id).where(AssetTeam.asset_id == asset_id)).scalars().all()
    )


def to_read(db: Session, a: Asset) -> dict:
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
        "assigned_user_ids": assigned_user_ids(db, a.id),
        "team_ids": team_ids(db, a.id),
    }


def _check_code_unique(db: Session, field, value: str | None, exclude_id: str | None) -> None:
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


def _sync_relations(db: Session, a: Asset, user_ids, team_ids_, company_id: str) -> None:
    if user_ids is not None:
        db.execute(delete(AssetUser).where(AssetUser.asset_id == a.id))
        for uid in dict.fromkeys(user_ids):
            db.add(AssetUser(asset_id=a.id, user_id=uid, company_id=company_id))
    if team_ids_ is not None:
        db.execute(delete(AssetTeam).where(AssetTeam.asset_id == a.id))
        for tid in dict.fromkeys(team_ids_):
            db.add(AssetTeam(asset_id=a.id, team_id=tid, company_id=company_id))


def create_asset(db: Session, payload: AssetCreate, company_id: str) -> Asset:
    _check_code_unique(db, Asset.barcode, payload.barcode, None)
    _check_code_unique(db, Asset.nfc_id, payload.nfc_id, None)
    seq = sequence_service.next_value(db, "asset", company_id)
    data = payload.model_dump(exclude={"assigned_user_ids", "team_ids"})
    a = Asset(custom_id=sequence_service.format_custom_id("A", seq), company_id=company_id, **data)
    db.add(a)
    db.flush()
    _sync_relations(db, a, payload.assigned_user_ids, payload.team_ids, company_id)
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
    if "parent_id" in data:
        _validate_parent(db, a.id, data["parent_id"])
    if "barcode" in data:
        _check_code_unique(db, Asset.barcode, data["barcode"], a.id)
    if "nfc_id" in data:
        _check_code_unique(db, Asset.nfc_id, data["nfc_id"], a.id)
    user_ids = data.pop("assigned_user_ids", None)
    team_ids_ = data.pop("team_ids", None)
    for k, v in data.items():
        setattr(a, k, v)
    _sync_relations(db, a, user_ids, team_ids_, company_id)
    db.commit()
    db.refresh(a)
    return a


def delete_asset(db: Session, a: Asset) -> None:
    if list_children(db, a.id):
        raise bad_request("ASSET_HAS_CHILDREN", "请先删除子资产")
    a.is_active = False
    a.deleted_at = utcnow()
    db.commit()


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
