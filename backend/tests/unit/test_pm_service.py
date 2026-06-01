from datetime import date

from sqlalchemy.orm import Session

from app.models.pm_frequency import PMFrequencyUnit
from app.schemas.pm import PMCreate, PMUpdate
from app.services import pm_service as svc

CO = "co-1"


def _payload(**kw):
    base = dict(
        title="月检",
        start_date=date(2026, 6, 1),
        frequency_unit=PMFrequencyUnit.MONTH,
        frequency_value=1,
    )
    base.update(kw)
    return PMCreate(**base)


def test_create_assigns_custom_id_and_next_due(db: Session):
    pm = svc.create_pm(
        db, _payload(assignee_ids=["u-1", "u-2"], team_ids=["t-1"]), CO, actor_user_id="admin"
    )
    assert pm.custom_id == "PM000001"
    assert pm.next_due_date == date(2026, 6, 1)
    assert set(svc.assignee_ids(db, pm.id)) == {"u-1", "u-2"}
    assert svc.team_ids(db, pm.id) == ["t-1"]
    acts = svc.list_activities(db, pm.id)
    assert any(a.activity_type == "CREATED" for a in acts)


def test_update_replaces_relations_and_resets_due_on_start_date(db: Session):
    pm = svc.create_pm(db, _payload(assignee_ids=["u-1"]), CO, actor_user_id="a")
    svc.update_pm(
        db, pm, PMUpdate(start_date=date(2026, 7, 15), assignee_ids=["u-9"]), CO, actor_user_id="a"
    )
    assert pm.next_due_date == date(2026, 7, 15)  # start_date 改 -> 重置
    assert svc.assignee_ids(db, pm.id) == ["u-9"]  # 关联全量替换


def test_update_frequency_only_keeps_next_due(db: Session):
    pm = svc.create_pm(db, _payload(), CO, actor_user_id="a")
    before = pm.next_due_date
    svc.update_pm(db, pm, PMUpdate(frequency_value=3), CO, actor_user_id="a")
    assert pm.next_due_date == before  # 仅改频率不动 next_due


def test_enable_disable_logs_activity(db: Session):
    pm = svc.create_pm(db, _payload(), CO, actor_user_id="a")
    svc.disable_pm(db, pm, CO, actor_user_id="a")
    assert pm.is_enabled is False
    svc.enable_pm(db, pm, CO, actor_user_id="a")
    assert pm.is_enabled is True
    types = [a.activity_type for a in svc.list_activities(db, pm.id)]
    assert "DISABLED" in types and "ENABLED" in types


def test_delete_soft(db: Session):
    pm = svc.create_pm(db, _payload(), CO, actor_user_id="a")
    svc.delete_pm(db, pm)
    assert svc.get_pm(db, pm.id) is None


def test_add_comment(db: Session):
    pm = svc.create_pm(db, _payload(), CO, actor_user_id="a")
    svc.add_comment(db, pm, "巡检备注", CO, actor_user_id="a")
    assert any(
        a.activity_type == "COMMENT" and a.comment == "巡检备注"
        for a in svc.list_activities(db, pm.id)
    )
