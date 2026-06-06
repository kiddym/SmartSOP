"""PM 排程增强字段（E6）：due_date_delay / ends_on / 到期前提醒 / 失效自停。"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm
from app.models.pm_frequency import PMFrequencyUnit
from app.models.user import User
from app.models.work_order import WorkOrder
from app.schemas.pm import PMCreate
from app.services import pm_service as svc
from app.tasks import pm_generate

CO = "co-1"


def _mk(db, **kw):
    base = dict(
        title="月检",
        start_date=date(2026, 6, 1),
        frequency_unit=PMFrequencyUnit.DAY,
        frequency_value=7,
    )
    base.update(kw)
    return svc.create_pm(db, PMCreate(**base), CO, actor_user_id="a")


# --------------------------------------------------------------------------- #
# 1) due_date_delay：工单 due_date = 生成日 + 延迟天数
# --------------------------------------------------------------------------- #
def test_due_date_delay_offsets_work_order_due(db: Session):
    pm = _mk(db, start_date=date(2026, 6, 1), due_date_delay=5)
    now = datetime(2026, 6, 1, 9, 0)
    wo = svc.generate_once(db, pm, actor_user_id=None, now=now, enforce_due=True)
    assert wo is not None
    assert wo.due_date == date(2026, 6, 6)  # 生成日 2026-06-01 + 5 天


def test_due_date_delay_zero_is_generation_day(db: Session):
    pm = _mk(db, start_date=date(2026, 6, 1))  # 默认 delay=0
    wo = svc.generate_once(
        db, pm, actor_user_id=None, now=datetime(2026, 6, 1, 9, 0), enforce_due=True
    )
    assert wo is not None
    assert wo.due_date == date(2026, 6, 1)


def test_due_date_delay_defaults_persist(db: Session):
    pm = _mk(db)
    assert pm.due_date_delay == 0
    assert pm.ends_on is None
    assert pm.consecutive_unresponded == 0


# --------------------------------------------------------------------------- #
# 2) ends_on：超过结束日不再生单并自动停用
# --------------------------------------------------------------------------- #
def test_ends_on_stops_generation_and_disables(db: Session):
    # next_due_date(=start) 已超过 ends_on -> 调度路径终止
    pm = _mk(db, start_date=date(2026, 6, 1), ends_on=date(2026, 5, 1))
    wo = svc.generate_once(
        db, pm, actor_user_id=None, now=datetime(2026, 6, 1, 9, 0), enforce_due=True
    )
    assert wo is None
    assert pm.is_enabled is False
    types = [a.activity_type for a in svc.list_activities(db, pm.id)]
    assert "ENDED" in types


def test_ends_on_before_cutoff_still_generates(db: Session):
    pm = _mk(db, start_date=date(2026, 6, 1), ends_on=date(2026, 12, 31))
    wo = svc.generate_once(
        db, pm, actor_user_id=None, now=datetime(2026, 6, 1, 9, 0), enforce_due=True
    )
    assert wo is not None
    assert pm.is_enabled is True


def test_ends_on_via_scan_marks_not_generated(db: Session):
    _mk(db, start_date=date(2026, 6, 1), ends_on=date(2026, 5, 1))
    summary = pm_generate.run(db, now=datetime(2026, 6, 1, 2, 0))
    assert summary["scanned"] == 1
    assert summary["generated"] == 0
    assert db.query(WorkOrder).count() == 0


# --------------------------------------------------------------------------- #
# 3) 失效自停：连续 N 张工单无人响应自动停用
# --------------------------------------------------------------------------- #
def test_auto_disable_after_consecutive_unresponded(db: Session):
    pm = _mk(db, start_date=date(2026, 1, 1), frequency_unit=PMFrequencyUnit.DAY, frequency_value=1)
    # 反复生成；每张 WO 默认 OPEN 且无 first_responded_at -> 计数累加。
    base = datetime(2026, 6, 1, 9, 0)
    disabled_at = None
    for i in range(svc.AUTO_DISABLE_THRESHOLD + 2):
        if not pm.is_enabled:
            break
        wo = svc.generate_once(
            db, pm, actor_user_id=None, now=base + timedelta(days=i), enforce_due=True
        )
        if wo is None:
            disabled_at = i
            break
    assert pm.is_enabled is False
    assert disabled_at is not None
    types = [a.activity_type for a in svc.list_activities(db, pm.id)]
    assert "AUTO_DISABLED" in types


def test_response_resets_unresponded_counter(db: Session):
    pm = _mk(db, start_date=date(2026, 1, 1), frequency_unit=PMFrequencyUnit.DAY, frequency_value=1)
    base = datetime(2026, 6, 1, 9, 0)
    # 第一次生成
    wo1 = svc.generate_once(db, pm, actor_user_id=None, now=base, enforce_due=True)
    assert wo1 is not None
    # 标记上一张已响应（first_responded_at 非空）
    wo1.first_responded_at = base
    db.commit()
    # 第二次生成应将计数归零（上一张被视为已响应）
    svc.generate_once(db, pm, actor_user_id=None, now=base + timedelta(days=1), enforce_due=True)
    assert pm.consecutive_unresponded == 0
    assert pm.is_enabled is True


# --------------------------------------------------------------------------- #
# 4) 到期前提醒（轻量）：days_before_pm_notification 窗口内给指派人发一次
# --------------------------------------------------------------------------- #
def _active_user(db, uid: str) -> User:
    u = User(id=uid, email=f"{uid}@x.cn", password_hash="x", name=uid, company_id=CO)
    db.add(u)
    db.commit()
    return u


def test_due_soon_reminder_fires_once(db: Session):
    from app.services import company_settings_service as css

    cs = css.get_or_create(db, CO)
    cs.days_before_pm_notification = 7
    db.commit()
    _active_user(db, "u-assignee")
    # next_due_date 在 5 天后（窗口内、尚未到期）
    today = date(2026, 6, 1)
    pm = _mk(db, start_date=today + timedelta(days=5), assignee_ids=["u-assignee"])
    assert pm.next_due_date == today + timedelta(days=5)

    fired = pm_generate._remind_upcoming(db, today=today)
    assert fired == 1
    notes = db.query(Notification).filter_by(type="PM_DUE_SOON").all()
    assert len(notes) == 1
    assert notes[0].recipient_user_id == "u-assignee"
    assert db.query(NotificationArm).count() == 1

    # 再扫一次：已 arm，去重不重发
    fired2 = pm_generate._remind_upcoming(db, today=today)
    assert fired2 == 0
    assert db.query(Notification).filter_by(type="PM_DUE_SOON").count() == 1


def test_due_soon_reminder_disabled_when_setting_zero(db: Session):
    _active_user(db, "u2")
    today = date(2026, 6, 1)
    _mk(db, start_date=today + timedelta(days=3), assignee_ids=["u2"])
    fired = pm_generate._remind_upcoming(db, today=today)
    assert fired == 0
    assert db.query(Notification).filter_by(type="PM_DUE_SOON").count() == 0
