from decimal import Decimal

from app.models.meter_comparator import MeterComparator as C
from app.services.meter_trigger_service import _condition_met, _decide


def test_condition_met_strict_inequality():
    assert _condition_met(C.MORE_THAN, Decimal("100.0001"), Decimal("100")) is True
    assert _condition_met(C.MORE_THAN, Decimal("100"), Decimal("100")) is False  # 相等不算
    assert _condition_met(C.LESS_THAN, Decimal("99.9999"), Decimal("100")) is True
    assert _condition_met(C.LESS_THAN, Decimal("100"), Decimal("100")) is False


def test_decide_fire_when_met_and_armed():
    assert _decide(is_armed=True, met=True) == "FIRE"


def test_decide_rearm_when_unmet_and_disarmed():
    assert _decide(is_armed=False, met=False) == "REARM"


def test_decide_noop_persisting_met():
    assert _decide(is_armed=False, met=True) == "NOOP"   # 持续满足，已发火抑制


def test_decide_noop_persisting_unmet():
    assert _decide(is_armed=True, met=False) == "NOOP"   # 持续未满足
