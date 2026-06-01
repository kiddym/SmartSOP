from datetime import date

from sqlalchemy.orm import Session

from app.models.pm_activity import PMActivity
from app.models.pm_frequency import PMFrequencyUnit
from app.models.preventive_maintenance import (
    PMAssignee,
    PMTeam,
    PreventiveMaintenance,
)
from app.models.work_order_status import WorkOrderPriority


def test_pm_row_roundtrip(db: Session):
    pm = PreventiveMaintenance(
        custom_id="PM000001",
        title="月检",
        company_id="co-1",
        priority=WorkOrderPriority.MEDIUM,
        start_date=date(2026, 6, 1),
        frequency_unit=PMFrequencyUnit.MONTH,
        frequency_value=1,
        next_due_date=date(2026, 6, 1),
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)
    assert pm.id and pm.is_active is True and pm.is_enabled is True
    db.add(PMAssignee(pm_id=pm.id, user_id="u-1", company_id="co-1"))
    db.add(PMTeam(pm_id=pm.id, team_id="t-1", company_id="co-1"))
    db.add(PMActivity(pm_id=pm.id, company_id="co-1", activity_type="CREATED"))
    db.commit()
    assert pm.last_generated_at is None and pm.last_work_order_id is None


def test_pm_exports_registered():
    import app.models as m

    for name in ("PreventiveMaintenance", "PMAssignee", "PMTeam", "PMActivity"):
        assert name in m.__all__ and hasattr(m, name)
