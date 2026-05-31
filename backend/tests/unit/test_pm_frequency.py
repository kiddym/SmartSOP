from app.models.pm_frequency import PMFrequencyUnit


def test_frequency_unit_values():
    assert PMFrequencyUnit.DAY.value == "DAY"
    assert PMFrequencyUnit.WEEK.value == "WEEK"
    assert PMFrequencyUnit.MONTH.value == "MONTH"
    assert {u.value for u in PMFrequencyUnit} == {"DAY", "WEEK", "MONTH"}
