"""计量 API（/api/v1/meters）：仪表、读数、触发器。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.billing.catalog import Feature
from app.deps import get_db, require_feature, require_permission
from app.errors import not_found
from app.models.meter import Meter
from app.models.meter_reading import MeterReading
from app.models.meter_trigger import MeterTrigger
from app.models.user import User
from app.schemas.meter import (
    MeterCreate,
    MeterRead,
    MeterReadingCreate,
    MeterReadingRead,
    MeterReadingUpdate,
    MeterUpdate,
    ReadingResult,
    TriggerCreate,
    TriggerRead,
    TriggerUpdate,
)
from app.services import meter_service as svc
from app.services import meter_trigger_service as ts

router = APIRouter(
    prefix="/api/v1/meters",
    tags=["meters"],
    dependencies=[Depends(require_feature(Feature.meters))],
)


def _ensure_meter(m: Meter | None, company_id: str) -> Meter:
    if m is None or m.company_id != company_id:
        raise not_found("METER_NOT_FOUND", "仪表不存在")
    return m


def _ensure_trigger(trig: MeterTrigger | None, meter_id: str, company_id: str) -> MeterTrigger:
    if trig is None or trig.company_id != company_id or trig.meter_id != meter_id:
        raise not_found("METER_TRIGGER_NOT_FOUND", "触发器不存在")
    return trig


def _ensure_reading(reading: MeterReading | None, meter_id: str, company_id: str) -> MeterReading:
    if reading is None or reading.company_id != company_id or reading.meter_id != meter_id:
        raise not_found("METER_READING_NOT_FOUND", "读数不存在")
    return reading


def _read_trigger(db: Session, trig: MeterTrigger) -> TriggerRead:
    data = TriggerRead.model_validate(trig)
    data.assignee_ids = ts.assignee_ids(db, trig.id)
    data.team_ids = ts.team_ids(db, trig.id)
    return data


# ---- 仪表 ----
@router.get("", response_model=list[MeterRead])
def list_meters(
    asset_id: str | None = None,
    location_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_VIEW)),
) -> list[dict[str, object]]:
    return [
        svc.to_read(db, m) for m in svc.list_meters(db, asset_id=asset_id, location_id=location_id)
    ]


@router.post("", response_model=MeterRead, status_code=status.HTTP_201_CREATED)
def create_meter(
    payload: MeterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_CREATE)),
) -> dict[str, object]:
    m = svc.create_meter(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return svc.to_read(db, m)


@router.get("/{meter_id}", response_model=MeterRead)
def get_meter(
    meter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_VIEW)),
) -> dict[str, object]:
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    return svc.to_read(db, m)


@router.patch("/{meter_id}", response_model=MeterRead)
def update_meter(
    meter_id: str,
    payload: MeterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_EDIT)),
) -> dict[str, object]:
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    m = svc.update_meter(db, m, payload, current_user.company_id, actor_user_id=current_user.id)
    return svc.to_read(db, m)


@router.delete("/{meter_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_meter(
    meter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_DELETE)),
) -> None:
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    svc.delete_meter(db, m)


# ---- 读数 ----
@router.get("/{meter_id}/readings", response_model=list[MeterReadingRead])
def list_readings(
    meter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.READING_VIEW)),
) -> list[MeterReading]:
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    return svc.list_readings(db, meter_id)


@router.post(
    "/{meter_id}/readings", response_model=ReadingResult, status_code=status.HTTP_201_CREATED
)
def submit_reading(
    meter_id: str,
    payload: MeterReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.READING_CREATE)),
) -> ReadingResult:
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    reading, wos = svc.submit_reading(
        db, m, payload, current_user.company_id, actor_user_id=current_user.id
    )
    return ReadingResult(
        reading=MeterReadingRead.model_validate(reading),
        generated_work_order_ids=[wo.id for wo in wos],
    )


@router.patch("/{meter_id}/readings/{reading_id}", response_model=MeterReadingRead)
def update_reading(
    meter_id: str,
    reading_id: str,
    payload: MeterReadingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.READING_CREATE)),
) -> MeterReading:
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    reading = _ensure_reading(svc.get_reading(db, reading_id), meter_id, current_user.company_id)
    return svc.update_reading(db, reading, m, payload)


@router.delete(
    "/{meter_id}/readings/{reading_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_reading(
    meter_id: str,
    reading_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.READING_CREATE)),
) -> None:
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    reading = _ensure_reading(svc.get_reading(db, reading_id), meter_id, current_user.company_id)
    svc.delete_reading(db, reading)


# ---- 触发器 ----
@router.get("/{meter_id}/triggers", response_model=list[TriggerRead])
def list_triggers(
    meter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_VIEW)),
) -> list[TriggerRead]:
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    return [_read_trigger(db, t) for t in ts.list_triggers(db, meter_id)]


@router.post(
    "/{meter_id}/triggers", response_model=TriggerRead, status_code=status.HTTP_201_CREATED
)
def create_trigger(
    meter_id: str,
    payload: TriggerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_CREATE)),
) -> TriggerRead:
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = ts.create_trigger(
        db, m.id, payload, current_user.company_id, actor_user_id=current_user.id
    )
    return _read_trigger(db, trig)


@router.get("/{meter_id}/triggers/{trigger_id}", response_model=TriggerRead)
def get_trigger(
    meter_id: str,
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_VIEW)),
) -> TriggerRead:
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    return _read_trigger(db, trig)


@router.patch("/{meter_id}/triggers/{trigger_id}", response_model=TriggerRead)
def update_trigger(
    meter_id: str,
    trigger_id: str,
    payload: TriggerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_EDIT)),
) -> TriggerRead:
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    ts.update_trigger(db, trig, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read_trigger(db, trig)


@router.delete(
    "/{meter_id}/triggers/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_trigger(
    meter_id: str,
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_DELETE)),
) -> None:
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    ts.delete_trigger(db, trig)


@router.post("/{meter_id}/triggers/{trigger_id}/enable", response_model=TriggerRead)
def enable_trigger(
    meter_id: str,
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_EDIT)),
) -> TriggerRead:
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    ts.enable_trigger(db, trig, current_user.company_id, actor_user_id=current_user.id)
    return _read_trigger(db, trig)


@router.post("/{meter_id}/triggers/{trigger_id}/disable", response_model=TriggerRead)
def disable_trigger(
    meter_id: str,
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_EDIT)),
) -> TriggerRead:
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    ts.disable_trigger(db, trig, current_user.company_id, actor_user_id=current_user.id)
    return _read_trigger(db, trig)
