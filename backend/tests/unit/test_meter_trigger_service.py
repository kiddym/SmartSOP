from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.meter_comparator import MeterComparator
from app.schemas.meter import TriggerCreate, TriggerUpdate
from app.services import meter_trigger_service as ts

CO = "co-1"


def _meter(db):
    m = Meter(custom_id="MTR000001", name="温度", unit="℃", company_id=CO)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _payload(**kw):
    base = dict(
        name="高温",
        comparator=MeterComparator.MORE_THAN,
        threshold=Decimal("100"),
        title="处理高温",
    )
    base.update(kw)
    return TriggerCreate(**base)


def test_create_trigger_armed_and_relations(db: Session):
    m = _meter(db)
    t = ts.create_trigger(
        db, m.id, _payload(assignee_ids=["u-1", "u-2"], team_ids=["t-1"]), CO, actor_user_id="a"
    )
    assert t.is_armed is True and t.is_enabled is True
    assert set(ts.assignee_ids(db, t.id)) == {"u-1", "u-2"}
    assert ts.team_ids(db, t.id) == ["t-1"]


def test_list_triggers_by_meter(db: Session):
    m = _meter(db)
    ts.create_trigger(db, m.id, _payload(name="A"), CO, actor_user_id="a")
    ts.create_trigger(db, m.id, _payload(name="B"), CO, actor_user_id="a")
    assert len(ts.list_triggers(db, m.id)) == 2


def test_update_threshold_rearms(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    t.is_armed = False
    db.commit()
    ts.update_trigger(db, t, TriggerUpdate(threshold=Decimal("200")), CO, actor_user_id="a")
    assert t.is_armed is True and t.threshold == Decimal("200")


def test_update_comparator_rearms(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    t.is_armed = False
    db.commit()
    ts.update_trigger(
        db, t, TriggerUpdate(comparator=MeterComparator.LESS_THAN), CO, actor_user_id="a"
    )
    assert t.is_armed is True


def test_update_presets_only_keeps_armed(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    t.is_armed = False
    db.commit()
    ts.update_trigger(
        db, t, TriggerUpdate(title="改标题", assignee_ids=["u-9"]), CO, actor_user_id="a"
    )
    assert t.is_armed is False  # 仅改预设不动武装
    assert ts.assignee_ids(db, t.id) == ["u-9"]  # 关联全量替换


def test_enable_disable(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    ts.disable_trigger(db, t, CO, actor_user_id="a")
    assert t.is_enabled is False
    ts.enable_trigger(db, t, CO, actor_user_id="a")
    assert t.is_enabled is True


def test_delete_soft(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    ts.delete_trigger(db, t)
    assert ts.get_trigger(db, t.id) is None
