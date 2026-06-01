from sqlalchemy.orm import Session

from app.schemas.meter import MeterCreate, MeterUpdate
from app.services import meter_service as svc

CO = "co-1"


def test_create_meter_assigns_custom_id(db: Session):
    m = svc.create_meter(
        db, MeterCreate(name="温度", unit="℃", update_frequency_days=7), CO, actor_user_id="a"
    )
    assert m.custom_id == "MTR000001"
    assert m.unit == "℃" and m.update_frequency_days == 7


def test_list_and_filter_meters(db: Session):
    svc.create_meter(db, MeterCreate(name="A", asset_id="as-1"), CO, actor_user_id="a")
    svc.create_meter(db, MeterCreate(name="B", asset_id="as-2"), CO, actor_user_id="a")
    assert len(svc.list_meters(db)) == 2
    got = svc.list_meters(db, asset_id="as-1")
    assert len(got) == 1 and got[0].name == "A"


def test_update_meter(db: Session):
    m = svc.create_meter(db, MeterCreate(name="温度"), CO, actor_user_id="a")
    svc.update_meter(db, m, MeterUpdate(name="改名", unit="bar"), CO, actor_user_id="a")
    assert m.name == "改名" and m.unit == "bar"


def test_delete_meter_soft(db: Session):
    m = svc.create_meter(db, MeterCreate(name="温度"), CO, actor_user_id="a")
    svc.delete_meter(db, m)
    assert svc.get_meter(db, m.id) is None


def test_list_readings_empty(db: Session):
    m = svc.create_meter(db, MeterCreate(name="温度"), CO, actor_user_id="a")
    assert svc.list_readings(db, m.id) == []
