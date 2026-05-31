"""仪表服务：Meter CRUD、customId、读数提交（同步评估触发器）、读数查询。

submit_reading 编排：插入读数→评估该 meter 全部启用 trigger（边沿决策）→
FIRE 生单、REARM 武装→commit。触发器评估委托 meter_trigger_service。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.meter import Meter
from app.models.meter_reading import MeterReading
from app.models.meter_trigger import MeterTrigger
from app.schemas.meter import MeterCreate, MeterReadingCreate, MeterUpdate
from app.services import meter_trigger_service as ts
from app.services import sequence_service


def create_meter(db: Session, payload: MeterCreate, company_id: str,
                 actor_user_id: str | None) -> Meter:
    seq = sequence_service.next_value(db, "meter", company_id)
    m = Meter(
        custom_id=sequence_service.format_custom_id("MTR", seq),
        name=payload.name, unit=payload.unit,
        update_frequency_days=payload.update_frequency_days,
        asset_id=payload.asset_id, location_id=payload.location_id,
        company_id=company_id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def list_meters(db: Session, *, asset_id: str | None = None,
                location_id: str | None = None) -> list[Meter]:
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


def update_meter(db: Session, m: Meter, payload: MeterUpdate, company_id: str,
                 actor_user_id: str | None) -> Meter:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


def delete_meter(db: Session, m: Meter) -> None:
    m.is_active = False
    m.deleted_at = utcnow()
    db.commit()


def list_readings(db: Session, meter_id: str) -> list[MeterReading]:
    return list(db.execute(
        select(MeterReading).where(MeterReading.meter_id == meter_id)
        .order_by(MeterReading.reading_at, MeterReading.id)).scalars().all())


def submit_reading(db: Session, m: Meter, payload: MeterReadingCreate, company_id: str,
                   actor_user_id: str | None):
    """插入读数并同步评估该 meter 全部启用 trigger（边沿决策）。

    返回 (reading, generated_work_orders)。FIRE 复用 generate_from_trigger 生单
    （内部 commit 工单）；trigger 状态与读数末尾统一 commit。
    """
    reading = MeterReading(
        meter_id=m.id, value=payload.value,
        reading_at=payload.reading_at or utcnow(),
        recorded_by_user_id=actor_user_id, company_id=company_id,
    )
    db.add(reading)
    db.flush()
    triggers = list(db.execute(
        select(MeterTrigger).where(
            MeterTrigger.meter_id == m.id,
            MeterTrigger.is_active.is_(True),
            MeterTrigger.is_enabled.is_(True),
        ).order_by(MeterTrigger.created_at, MeterTrigger.id)).scalars().all())
    generated = []
    for trig in triggers:
        met = ts._condition_met(trig.comparator, reading.value, trig.threshold)
        action = ts._decide(is_armed=trig.is_armed, met=met)
        if action == "FIRE":
            wo = ts.generate_from_trigger(db, trig, reading=reading,
                                          actor_user_id=actor_user_id)
            generated.append(wo)
        elif action == "REARM":
            trig.is_armed = True
    db.commit()
    db.refresh(reading)
    return reading, generated
