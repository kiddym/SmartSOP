"""仪表服务：Meter CRUD、customId、读数提交（同步评估触发器）、读数查询。

submit_reading 编排：插入读数→评估该 meter 全部启用 trigger（边沿决策）→
FIRE 生单、REARM 武装→commit。触发器评估委托 meter_trigger_service。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import not_found, unprocessable
from app.models.base import utcnow
from app.models.meter import Meter, MeterUser
from app.models.meter_reading import MeterReading
from app.models.meter_trigger import MeterTrigger
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder
from app.schemas.meter import (
    MeterCreate,
    MeterReadingCreate,
    MeterReadingUpdate,
    MeterUpdate,
)
from app.services import meter_trigger_service as ts
from app.services import sequence_service


def user_ids(db: Session, meter_id: str) -> list[str]:
    return list(
        db.execute(
            select(MeterUser.user_id)
            .where(MeterUser.meter_id == meter_id)
            .order_by(MeterUser.user_id)
        )
        .scalars()
        .all()
    )


def to_read(db: Session, m: Meter) -> dict[str, object]:
    return {
        "id": m.id,
        "custom_id": m.custom_id,
        "name": m.name,
        "unit": m.unit,
        "update_frequency_days": m.update_frequency_days,
        "asset_id": m.asset_id,
        "location_id": m.location_id,
        "meter_category_id": m.meter_category_id,
        "image_url": m.image_url,
        "user_ids": user_ids(db, m.id),
    }


def _validate_users(db: Session, ids: list[str] | None, company_id: str) -> None:
    """校验关注人归属当前租户（不存在/非 active/他租户均 404）。"""
    if ids is None:
        return
    for uid in dict.fromkeys(ids):
        u = db.get(User, uid)
        if u is None or u.company_id != company_id or u.status != UserStatus.active:
            raise not_found("USER_NOT_FOUND", "用户不存在")


def _sync_users(db: Session, m: Meter, ids: list[str] | None, company_id: str) -> None:
    if ids is None:
        return
    db.execute(delete(MeterUser).where(MeterUser.meter_id == m.id))
    for uid in dict.fromkeys(ids):
        db.add(MeterUser(meter_id=m.id, user_id=uid, company_id=company_id))


def create_meter(
    db: Session, payload: MeterCreate, company_id: str, actor_user_id: str | None
) -> Meter:
    _validate_users(db, payload.user_ids, company_id)
    seq = sequence_service.next_value(db, "meter", company_id)
    m = Meter(
        custom_id=sequence_service.format_custom_id("MTR", seq),
        name=payload.name,
        unit=payload.unit,
        update_frequency_days=payload.update_frequency_days,
        asset_id=payload.asset_id,
        location_id=payload.location_id,
        meter_category_id=payload.meter_category_id,
        image_url=payload.image_url,
        company_id=company_id,
    )
    db.add(m)
    db.flush()
    _sync_users(db, m, payload.user_ids, company_id)
    db.commit()
    db.refresh(m)
    return m


def list_meters(
    db: Session, *, asset_id: str | None = None, location_id: str | None = None
) -> list[Meter]:
    stmt = select(Meter).where(Meter.is_active.is_(True))
    if asset_id is not None:
        stmt = stmt.where(Meter.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(Meter.location_id == location_id)
    return list(db.execute(stmt.order_by(Meter.custom_id)).scalars().all())


def get_meter(db: Session, meter_id: str) -> Meter | None:
    m = db.get(Meter, meter_id)
    if m is None or not m.is_active:
        return None
    return m


def update_meter(
    db: Session, m: Meter, payload: MeterUpdate, company_id: str, actor_user_id: str | None
) -> Meter:
    data = payload.model_dump(exclude_unset=True)
    new_user_ids = data.pop("user_ids", None)
    _validate_users(db, new_user_ids, company_id)
    for k, v in data.items():
        setattr(m, k, v)
    _sync_users(db, m, new_user_ids, company_id)
    db.commit()
    db.refresh(m)
    return m


def delete_meter(db: Session, m: Meter) -> None:
    m.is_active = False
    m.deleted_at = utcnow()
    db.commit()


def list_readings(db: Session, meter_id: str) -> list[MeterReading]:
    return list(
        db.execute(
            select(MeterReading)
            .where(MeterReading.meter_id == meter_id)
            .order_by(MeterReading.reading_at, MeterReading.id)
        )
        .scalars()
        .all()
    )


def get_reading(db: Session, reading_id: str) -> MeterReading | None:
    return db.get(MeterReading, reading_id)


def _latest_reading(
    db: Session, meter_id: str, *, exclude_id: str | None = None
) -> MeterReading | None:
    stmt = select(MeterReading).where(MeterReading.meter_id == meter_id)
    if exclude_id is not None:
        stmt = stmt.where(MeterReading.id != exclude_id)
    stmt = stmt.order_by(MeterReading.reading_at.desc(), MeterReading.id.desc())
    return db.execute(stmt).scalars().first()


def _assert_frequency_respected(
    db: Session, m: Meter, reading_at: datetime, *, exclude_id: str | None = None
) -> None:
    """软频率校验：仅当 update_frequency_days 为正才生效。

    若已有读数且本次读数时刻距最近一条读数不足 update_frequency_days 天，拒绝。
    update_frequency_days 为 None/0 时直接返回（不校验）。
    """
    freq = m.update_frequency_days
    if not freq or freq <= 0:
        return
    last = _latest_reading(db, m.id, exclude_id=exclude_id)
    if last is None:
        return
    if abs(reading_at - last.reading_at) < timedelta(days=freq):
        raise unprocessable(
            "READING_FREQUENCY_NOT_RESPECTED",
            f"读数过于频繁：该计量要求每 {freq} 天最多一条读数",
        )


def update_reading(
    db: Session, reading: MeterReading, m: Meter, payload: MeterReadingUpdate
) -> MeterReading:
    data = payload.model_dump(exclude_unset=True)
    new_at = data.get("reading_at", reading.reading_at)
    if "reading_at" in data:
        _assert_frequency_respected(db, m, new_at, exclude_id=reading.id)
    for k, v in data.items():
        setattr(reading, k, v)
    db.commit()
    db.refresh(reading)
    return reading


def delete_reading(db: Session, reading: MeterReading) -> None:
    db.delete(reading)
    db.commit()


def submit_reading(
    db: Session, m: Meter, payload: MeterReadingCreate, company_id: str, actor_user_id: str | None
) -> tuple[MeterReading, list[WorkOrder]]:
    """插入读数并同步评估该 meter 全部启用 trigger（边沿决策）。

    返回 (reading, generated_work_orders)。FIRE 复用 generate_from_trigger 生单
    （内部 commit 工单）；trigger 状态与读数末尾统一 commit。

    频率校验（软）：仅当 meter.update_frequency_days 为正时生效——若本次读数时刻
    距上一条读数不足该天数，拒绝（422 READING_FREQUENCY_NOT_RESPECTED）。
    update_frequency_days 为 None/0 时不校验，既有读数测试不受影响。
    """
    reading_at = payload.reading_at or utcnow()
    _assert_frequency_respected(db, m, reading_at)
    reading = MeterReading(
        meter_id=m.id,
        value=payload.value,
        reading_at=reading_at,
        recorded_by_user_id=actor_user_id,
        company_id=company_id,
    )
    db.add(reading)
    db.flush()
    triggers = list(
        db.execute(
            select(MeterTrigger)
            .where(
                MeterTrigger.meter_id == m.id,
                MeterTrigger.is_active.is_(True),
                MeterTrigger.is_enabled.is_(True),
            )
            .order_by(MeterTrigger.created_at, MeterTrigger.id)
        )
        .scalars()
        .all()
    )
    generated = []
    for trig in triggers:
        met = ts._condition_met(trig.comparator, reading.value, trig.threshold)
        action = ts._decide(is_armed=trig.is_armed, met=met)
        if action == "FIRE":
            wo = ts.generate_from_trigger(db, trig, reading=reading, actor_user_id=actor_user_id)
            generated.append(wo)
        elif action == "REARM":
            trig.is_armed = True
    db.commit()
    db.refresh(reading)
    return reading, generated
