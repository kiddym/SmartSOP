from app.models.meter_comparator import MeterComparator


def test_comparator_values():
    assert MeterComparator.LESS_THAN.value == "LESS_THAN"
    assert MeterComparator.MORE_THAN.value == "MORE_THAN"
    assert {c.value for c in MeterComparator} == {"LESS_THAN", "MORE_THAN"}
