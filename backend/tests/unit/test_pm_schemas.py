import pytest
from pydantic import ValidationError

from app.models.pm_frequency import PMFrequencyUnit
from app.schemas.pm import PMCreate, PMUpdate


def test_pm_create_defaults():
    p = PMCreate(title="月检", start_date="2026-06-01",
                 frequency_unit="MONTH", frequency_value=1)
    assert p.frequency_unit == PMFrequencyUnit.MONTH
    assert p.assignee_ids == [] and p.team_ids == []
    assert p.priority.value == "NONE"


def test_pm_create_rejects_blank_title():
    with pytest.raises(ValidationError):
        PMCreate(title="", start_date="2026-06-01",
                 frequency_unit="DAY", frequency_value=1)


def test_pm_update_all_optional():
    u = PMUpdate()
    assert u.model_dump(exclude_unset=True) == {}
