"""位置服务：树（防环）、customId、负责人/团队关联。"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.base import utcnow
from app.models.location import Location, LocationTeam, LocationUser
from app.schemas.location import LocationCreate, LocationUpdate
from app.services import sequence_service


def _user_ids(db: Session, location_id: str) -> list[str]:
    return list(db.execute(
        select(LocationUser.user_id).where(LocationUser.location_id == location_id)
    ).scalars().all())


def _team_ids(db: Session, location_id: str) -> list[str]:
    return list(db.execute(
        select(LocationTeam.team_id).where(LocationTeam.location_id == location_id)
    ).scalars().all())


def to_read(db: Session, loc: Location) -> dict:
    return {
        "id": loc.id, "custom_id": loc.custom_id, "name": loc.name,
        "description": loc.description, "parent_id": loc.parent_id,
        "address": loc.address, "longitude": loc.longitude, "latitude": loc.latitude,
        "assigned_user_ids": _user_ids(db, loc.id), "team_ids": _team_ids(db, loc.id),
    }


def _descendant_ids(db: Session, location_id: str) -> set[str]:
    """收集 location_id 的所有后代 id（活跃）。"""
    out: set[str] = set()
    frontier = [location_id]
    while frontier:
        rows = db.execute(
            select(Location.id).where(
                Location.parent_id.in_(frontier), Location.is_active.is_(True)
            )
        ).scalars().all()
        rows = [r for r in rows if r not in out]
        out.update(rows)
        frontier = rows
    return out


def _validate_parent(db: Session, loc_id: str, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if parent_id == loc_id:
        raise bad_request("LOCATION_CYCLE", "父位置不能是自身")
    if parent_id in _descendant_ids(db, loc_id):
        raise bad_request("LOCATION_CYCLE", "父位置不能是自身的后代")


def _sync_relations(db: Session, loc: Location, user_ids, team_ids, company_id: str) -> None:
    if user_ids is not None:
        db.execute(delete(LocationUser).where(LocationUser.location_id == loc.id))
        for uid in dict.fromkeys(user_ids):
            db.add(LocationUser(location_id=loc.id, user_id=uid, company_id=company_id))
    if team_ids is not None:
        db.execute(delete(LocationTeam).where(LocationTeam.location_id == loc.id))
        for tid in dict.fromkeys(team_ids):
            db.add(LocationTeam(location_id=loc.id, team_id=tid, company_id=company_id))


def create_location(db: Session, payload: LocationCreate, company_id: str) -> Location:
    seq = sequence_service.next_value(db, "location", company_id)
    loc = Location(
        custom_id=sequence_service.format_custom_id("L", seq),
        name=payload.name, description=payload.description, parent_id=payload.parent_id,
        address=payload.address, longitude=payload.longitude, latitude=payload.latitude,
        company_id=company_id,
    )
    db.add(loc)
    db.flush()
    _sync_relations(db, loc, payload.assigned_user_ids, payload.team_ids, company_id)
    db.commit()
    db.refresh(loc)
    return loc


def list_locations(db: Session, parent_id: str | None = None) -> list[Location]:
    stmt = select(Location).where(Location.is_active.is_(True))
    if parent_id is not None:
        stmt = stmt.where(Location.parent_id == parent_id)
    return list(db.execute(stmt).scalars().all())


def list_children(db: Session, location_id: str) -> list[Location]:
    return list(db.execute(
        select(Location).where(
            Location.parent_id == location_id, Location.is_active.is_(True)
        )
    ).scalars().all())


def get_location(db: Session, location_id: str) -> Location | None:
    loc = db.get(Location, location_id)
    if loc is None or not loc.is_active:
        return None
    return loc


def update_location(db: Session, loc: Location, payload: LocationUpdate, company_id: str) -> Location:
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        _validate_parent(db, loc.id, data["parent_id"])
    user_ids = data.pop("assigned_user_ids", None)
    team_ids = data.pop("team_ids", None)
    for k, v in data.items():
        setattr(loc, k, v)
    _sync_relations(db, loc, user_ids, team_ids, company_id)
    db.commit()
    db.refresh(loc)
    return loc


def delete_location(db: Session, loc: Location) -> None:
    if list_children(db, loc.id):
        raise bad_request("LOCATION_HAS_CHILDREN", "请先删除子位置")
    loc.is_active = False
    loc.deleted_at = utcnow()
    db.commit()
