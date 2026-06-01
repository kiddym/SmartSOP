"""位置 API（/api/v1/locations）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.location import Location
from app.models.user import User
from app.schemas.location import LocationCreate, LocationMini, LocationRead, LocationUpdate
from app.services import location_service

router = APIRouter(prefix="/api/v1/locations", tags=["locations"])


def _ensure(loc: Location | None, company_id: str) -> Location:
    if loc is None or loc.company_id != company_id:
        raise not_found("LOCATION_NOT_FOUND", "位置不存在")
    return loc


@router.get("", response_model=list[LocationRead])
def list_locations(
    parent_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_VIEW)),
) -> list[dict[str, object]]:
    return [location_service.to_read(db, x) for x in location_service.list_locations(db, parent_id)]


@router.get("/mini", response_model=list[LocationMini])
def list_mini(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_VIEW)),
) -> list[Location]:
    return location_service.list_locations(db)


@router.post("", response_model=LocationRead, status_code=201)
def create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_CREATE)),
) -> dict[str, object]:
    loc = location_service.create_location(db, payload, current_user.company_id)
    return location_service.to_read(db, loc)


@router.get("/{location_id}", response_model=LocationRead)
def get_location(
    location_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_VIEW)),
) -> dict[str, object]:
    loc = _ensure(location_service.get_location(db, location_id), current_user.company_id)
    return location_service.to_read(db, loc)


@router.get("/{location_id}/children", response_model=list[LocationRead])
def list_children(
    location_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_VIEW)),
) -> list[dict[str, object]]:
    _ensure(location_service.get_location(db, location_id), current_user.company_id)
    return [
        location_service.to_read(db, x) for x in location_service.list_children(db, location_id)
    ]


@router.patch("/{location_id}", response_model=LocationRead)
def update_location(
    location_id: str,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_EDIT)),
) -> dict[str, object]:
    loc = _ensure(location_service.get_location(db, location_id), current_user.company_id)
    loc = location_service.update_location(db, loc, payload, current_user.company_id)
    return location_service.to_read(db, loc)


@router.delete("/{location_id}", status_code=204, response_model=None)
def delete_location(
    location_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_DELETE)),
) -> None:
    loc = _ensure(location_service.get_location(db, location_id), current_user.company_id)
    location_service.delete_location(db, loc)
