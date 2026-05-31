from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.meter_comparator import MeterComparator
from app.schemas.meter import MeterCreate, TriggerCreate, TriggerUpdate, MeterReadingCreate


def test_meter_create_defaults():
    m = MeterCreate(name="温度表", unit="℃")
    assert m.unit == "℃" and m.update_frequency_days is None
    assert m.asset_id is None


def test_meter_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        MeterCreate(name="", unit="℃")


def test_trigger_create_defaults():
    t = TriggerCreate(name="高温", comparator="MORE_THAN", threshold=Decimal("100"),
                      title="处理高温")
    assert t.comparator == MeterComparator.MORE_THAN
    assert t.priority.value == "NONE"
    assert t.assignee_ids == [] and t.team_ids == []


def test_trigger_update_all_optional():
    assert TriggerUpdate().model_dump(exclude_unset=True) == {}


def test_reading_create_requires_value():
    r = MeterReadingCreate(value=Decimal("12.5"))
    assert r.value == Decimal("12.5") and r.reading_at is None
    with pytest.raises(ValidationError):
        MeterReadingCreate()
