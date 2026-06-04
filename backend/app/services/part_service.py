"""备件服务：Part CRUD（customId PRT）、M:N 关联（指派/团队/资产，全量替换）、列表过滤。

quantity 可经 update 直接改（入库/校正）；WO 消耗走 part_consumption_service。
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.base import utcnow
from app.models.location import Location
from app.models.part import Part, PartAsset, PartAssignee, PartLocation, PartPM, PartTeam
from app.models.preventive_maintenance import PreventiveMaintenance
from app.schemas.part import PartCreate, PartUpdate
from app.services import sequence_service


def assignee_ids(db: Session, part_id: str) -> list[str]:
    return list(
        db.execute(
            select(PartAssignee.user_id)
            .where(PartAssignee.part_id == part_id)
            .order_by(PartAssignee.user_id)
        )
        .scalars()
        .all()
    )


def team_ids(db: Session, part_id: str) -> list[str]:
    return list(
        db.execute(
            select(PartTeam.team_id).where(PartTeam.part_id == part_id).order_by(PartTeam.team_id)
        )
        .scalars()
        .all()
    )


def asset_ids(db: Session, part_id: str) -> list[str]:
    return list(
        db.execute(
            select(PartAsset.asset_id)
            .where(PartAsset.part_id == part_id)
            .order_by(PartAsset.asset_id)
        )
        .scalars()
        .all()
    )


def location_ids(db: Session, part_id: str) -> list[str]:
    return list(
        db.execute(
            select(PartLocation.location_id)
            .where(PartLocation.part_id == part_id)
            .order_by(PartLocation.location_id)
        )
        .scalars()
        .all()
    )


def pm_ids(db: Session, part_id: str) -> list[str]:
    return list(
        db.execute(select(PartPM.pm_id).where(PartPM.part_id == part_id).order_by(PartPM.pm_id))
        .scalars()
        .all()
    )


def _validate_pm_ids(db: Session, ids: list[str], company_id: str) -> None:
    # 守红线：目标 PM 必须属当前 company（且未软删），否则跨租户引用 → 404
    for pid in dict.fromkeys(ids):
        pm = db.get(PreventiveMaintenance, pid)
        if pm is None or not pm.is_active or pm.company_id != company_id:
            raise not_found("PREVENTIVE_MAINTENANCE_NOT_FOUND", "预防性维护不存在")


def _validate_location_ids(db: Session, ids: list[str], company_id: str) -> None:
    # 守红线：目标位置必须属当前 company（且未软删），否则跨租户引用 → 404
    for lid in dict.fromkeys(ids):
        loc = db.get(Location, lid)
        if loc is None or not loc.is_active or loc.company_id != company_id:
            raise not_found("LOCATION_NOT_FOUND", "位置不存在")


def _set_relations(
    db: Session,
    part_id: str,
    company_id: str,
    user_ids: list[str],
    team_id_list: list[str],
    asset_id_list: list[str],
    location_id_list: list[str],
    pm_id_list: list[str],
) -> None:
    for uid in dict.fromkeys(user_ids):
        db.add(PartAssignee(part_id=part_id, user_id=uid, company_id=company_id))
    for tid in dict.fromkeys(team_id_list):
        db.add(PartTeam(part_id=part_id, team_id=tid, company_id=company_id))
    for aid in dict.fromkeys(asset_id_list):
        db.add(PartAsset(part_id=part_id, asset_id=aid, company_id=company_id))
    for lid in dict.fromkeys(location_id_list):
        db.add(PartLocation(part_id=part_id, location_id=lid, company_id=company_id))
    for pid in dict.fromkeys(pm_id_list):
        db.add(PartPM(part_id=part_id, pm_id=pid, company_id=company_id))


def create_part(
    db: Session, payload: PartCreate, company_id: str, actor_user_id: str | None
) -> Part:
    seq = sequence_service.next_value(db, "part", company_id)
    p = Part(
        custom_id=sequence_service.format_custom_id("PRT", seq),
        name=payload.name,
        description=payload.description,
        cost=payload.cost,
        quantity=payload.quantity,
        min_quantity=payload.min_quantity,
        unit=payload.unit,
        barcode=payload.barcode,
        non_stock=payload.non_stock,
        category_id=payload.category_id,
        company_id=company_id,
    )
    db.add(p)
    db.flush()
    _validate_location_ids(db, payload.location_ids, company_id)
    _validate_pm_ids(db, payload.pm_ids, company_id)
    _set_relations(
        db,
        p.id,
        company_id,
        payload.assignee_ids,
        payload.team_ids,
        payload.asset_ids,
        payload.location_ids,
        payload.pm_ids,
    )
    db.commit()
    db.refresh(p)
    return p


def list_parts(
    db: Session,
    *,
    category_id: str | None = None,
    asset_id: str | None = None,
    low_stock: bool | None = None,
) -> list[Part]:
    stmt = select(Part).where(Part.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(Part.category_id == category_id)
    if asset_id is not None:
        stmt = stmt.where(
            Part.id.in_(select(PartAsset.part_id).where(PartAsset.asset_id == asset_id))
        )
    if low_stock is True:
        stmt = stmt.where(Part.non_stock.is_(False), Part.quantity < Part.min_quantity)
    return list(db.execute(stmt.order_by(Part.custom_id)).scalars().all())


def get_part(db: Session, part_id: str) -> Part | None:
    p = db.get(Part, part_id)
    if p is None or not p.is_active:
        return None
    return p


def update_part(
    db: Session, p: Part, payload: PartUpdate, company_id: str, actor_user_id: str | None
) -> Part:
    data = payload.model_dump(exclude_unset=True)
    new_assignees = data.pop("assignee_ids", None)
    new_teams = data.pop("team_ids", None)
    new_assets = data.pop("asset_ids", None)
    new_locations = data.pop("location_ids", None)
    new_pms = data.pop("pm_ids", None)
    for k, v in data.items():
        setattr(p, k, v)
    if new_assignees is not None:
        db.execute(delete(PartAssignee).where(PartAssignee.part_id == p.id))
        for uid in dict.fromkeys(new_assignees):
            db.add(PartAssignee(part_id=p.id, user_id=uid, company_id=company_id))
    if new_teams is not None:
        db.execute(delete(PartTeam).where(PartTeam.part_id == p.id))
        for tid in dict.fromkeys(new_teams):
            db.add(PartTeam(part_id=p.id, team_id=tid, company_id=company_id))
    if new_assets is not None:
        db.execute(delete(PartAsset).where(PartAsset.part_id == p.id))
        for aid in dict.fromkeys(new_assets):
            db.add(PartAsset(part_id=p.id, asset_id=aid, company_id=company_id))
    if new_locations is not None:
        _validate_location_ids(db, new_locations, company_id)
        db.execute(delete(PartLocation).where(PartLocation.part_id == p.id))
        for lid in dict.fromkeys(new_locations):
            db.add(PartLocation(part_id=p.id, location_id=lid, company_id=company_id))
    if new_pms is not None:
        _validate_pm_ids(db, new_pms, company_id)
        db.execute(delete(PartPM).where(PartPM.part_id == p.id))
        for pid in dict.fromkeys(new_pms):
            db.add(PartPM(part_id=p.id, pm_id=pid, company_id=company_id))
    db.commit()
    db.refresh(p)
    return p


def delete_part(db: Session, p: Part) -> None:
    p.is_active = False
    p.deleted_at = utcnow()
    db.commit()
