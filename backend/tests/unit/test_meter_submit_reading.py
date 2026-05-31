from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.meter_comparator import MeterComparator
from app.models.work_order import WorkOrder
from app.schemas.meter import MeterCreate, MeterReadingCreate, TriggerCreate
from app.services import meter_service as svc
from app.services import meter_trigger_service as ts

CO = "co-1"


def _meter_with_trigger(db, **trig_kw):
    m = svc.create_meter(db, MeterCreate(name="温度", unit="℃"), CO, actor_user_id="a")
    base = dict(name="高温", comparator=MeterComparator.MORE_THAN,
                threshold=Decimal("100"), title="处理高温")
    base.update(trig_kw)
    t = ts.create_trigger(db, m.id, TriggerCreate(**base), CO, actor_user_id="a")
    return m, t


def test_reading_below_threshold_no_wo(db: Session):
    m, t = _meter_with_trigger(db)
    reading, wos = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("50")),
                                      CO, actor_user_id="a")
    assert wos == []
    db.refresh(t)
    assert t.is_armed is True                        # 未满足，保持武装
    assert db.query(WorkOrder).count() == 0


def test_reading_crosses_threshold_fires_once(db: Session):
    m, t = _meter_with_trigger(db)
    _, wos1 = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")),
                                 CO, actor_user_id="a")
    assert len(wos1) == 1
    db.refresh(t)
    assert t.is_armed is False                       # 发火后解除武装
    # 持续超阈：不重复发火
    _, wos2 = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("160")),
                                 CO, actor_user_id="a")
    assert wos2 == []
    assert db.query(WorkOrder).count() == 1


def test_reading_falls_back_then_rearms_and_refires(db: Session):
    m, t = _meter_with_trigger(db)
    svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")), CO, actor_user_id="a")
    svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("50")), CO, actor_user_id="a")
    db.refresh(t)
    assert t.is_armed is True                         # 回落重新武装
    _, wos = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")),
                                CO, actor_user_id="a")
    assert len(wos) == 1                              # 再次发火
    assert db.query(WorkOrder).count() == 2


def test_disabled_trigger_skipped(db: Session):
    m, t = _meter_with_trigger(db)
    ts.disable_trigger(db, t, CO, actor_user_id="a")
    _, wos = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")),
                                CO, actor_user_id="a")
    assert wos == []
    db.refresh(t)
    assert t.is_armed is True                         # disabled 既不发火也不改武装态


def test_one_reading_multiple_triggers(db: Session):
    m, _ = _meter_with_trigger(db, name="高温50", threshold=Decimal("50"))
    ts.create_trigger(db, m.id, TriggerCreate(
        name="高温100", comparator=MeterComparator.MORE_THAN,
        threshold=Decimal("100"), title="处理"), CO, actor_user_id="a")
    _, wos = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")),
                                CO, actor_user_id="a")
    assert len(wos) == 2                              # 两个 trigger 同时满足
    assert db.query(WorkOrder).count() == 2
