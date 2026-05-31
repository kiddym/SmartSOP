from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.meter_comparator import MeterComparator
from app.models.meter_reading import MeterReading
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.schemas.meter import TriggerCreate
from app.services import meter_trigger_service as ts

CO = "co-1"


def _meter(db):
    m = Meter(custom_id="MTR000001", name="温度", unit="℃", company_id=CO)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_generate_from_trigger_creates_wo_and_disarms(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, TriggerCreate(
        name="高温", comparator=MeterComparator.MORE_THAN, threshold=Decimal("100"),
        title="处理高温", assignee_ids=["u-1"], team_ids=["t-1"], primary_user_id="pu",
    ), CO, actor_user_id="a")
    reading = MeterReading(meter_id=m.id, value=Decimal("150"), company_id=CO,
                           reading_at=datetime(2026, 6, 1, 9, 0))
    db.add(reading)
    db.flush()
    wo = ts.generate_from_trigger(db, t, reading=reading, actor_user_id=None)
    assert isinstance(wo, WorkOrder)
    assert wo.title == "处理高温" and wo.primary_user_id == "pu"
    assert wo.due_date is None                       # 反应式工单无截止日
    assert t.is_armed is False                       # 发火后解除武装
    assert t.last_work_order_id == wo.id
    assert t.last_triggered_at == datetime(2026, 6, 1, 9, 0)
    a = db.query(WorkOrderAssignee).filter_by(work_order_id=wo.id).all()
    tm = db.query(WorkOrderTeam).filter_by(work_order_id=wo.id).all()
    assert {x.user_id for x in a} == {"u-1"}
    assert {x.team_id for x in tm} == {"t-1"}
