from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.meter_comparator import MeterComparator
from app.models.meter_reading import MeterReading
from app.models.meter_trigger import (
    MeterTrigger,
    MeterTriggerAssignee,
    MeterTriggerTeam,
)
from app.models.work_order_status import WorkOrderPriority


def test_meter_row_roundtrip(db: Session):
    m = Meter(
        custom_id="MTR000001", name="主轴温度", unit="℃", update_frequency_days=7, company_id="co-1"
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    assert m.id and m.is_active is True
    db.add(MeterReading(meter_id=m.id, value=Decimal("123.4500"), company_id="co-1"))
    trig = MeterTrigger(
        meter_id=m.id,
        name="高温",
        comparator=MeterComparator.MORE_THAN,
        threshold=Decimal("100.0000"),
        priority=WorkOrderPriority.HIGH,
        title="高温处理",
        company_id="co-1",
    )
    db.add(trig)
    db.commit()
    db.refresh(trig)
    assert trig.is_armed is True and trig.is_enabled is True
    assert trig.last_triggered_at is None and trig.last_work_order_id is None
    db.add(MeterTriggerAssignee(trigger_id=trig.id, user_id="u-1", company_id="co-1"))
    db.add(MeterTriggerTeam(trigger_id=trig.id, team_id="t-1", company_id="co-1"))
    db.commit()
    reading = db.query(MeterReading).filter_by(meter_id=m.id).one()
    assert reading.reading_at is not None  # default utcnow


def test_meter_exports_registered():
    import app.models as mod

    for name in (
        "Meter",
        "MeterReading",
        "MeterTrigger",
        "MeterTriggerAssignee",
        "MeterTriggerTeam",
    ):
        assert name in mod.__all__ and hasattr(mod, name)
