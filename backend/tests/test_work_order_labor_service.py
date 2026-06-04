from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.models.time_category import TimeCategory
from app.models.work_order import WorkOrder
from app.schemas.work_order_cost import LaborCreate, LaborRead, LaborTimerStart, LaborUpdate
from app.services import sequence_service
from app.services import work_order_labor_service as labor


def _company(db, slug="acme"):
    c = Company(name=slug.title(), slug=slug)
    db.add(c)
    db.commit()
    tenant.set_current_company_id(c.id)
    return c.id


def _wo(db, company_id, title="检修"):
    seq = sequence_service.next_value(db, "work_order", company_id)
    wo = WorkOrder(
        custom_id=sequence_service.format_custom_id("WO", seq),
        title=title,
        company_id=company_id,
    )
    db.add(wo)
    db.commit()
    return wo


def test_manual_labor_cost(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.create_labor(
        db,
        wo,
        LaborCreate(duration_seconds=3600, hourly_rate=Decimal("80")),
        cid,
        actor_user_id=None,
    )
    assert row.duration_seconds == 3600
    assert row.hourly_rate == Decimal("80")
    assert labor.compute_cost(row) == Decimal("80.00")


def test_rate_defaults_from_category(db):
    cid = _company(db)
    wo = _wo(db, cid)
    cat = TimeCategory(name="常规", hourly_rate=Decimal("100"), company_id=cid)
    db.add(cat)
    db.commit()
    row = labor.create_labor(
        db, wo, LaborCreate(duration_seconds=1800, time_category_id=cat.id), cid, actor_user_id=None
    )
    assert row.hourly_rate == Decimal("100")
    assert labor.compute_cost(row) == Decimal("50.00")


def test_explicit_rate_overrides_category(db):
    cid = _company(db)
    wo = _wo(db, cid)
    cat = TimeCategory(name="常规", hourly_rate=Decimal("100"), company_id=cid)
    db.add(cat)
    db.commit()
    row = labor.create_labor(
        db,
        wo,
        LaborCreate(duration_seconds=3600, time_category_id=cat.id, hourly_rate=Decimal("60")),
        cid,
        actor_user_id=None,
    )
    assert row.hourly_rate == Decimal("60")


def test_category_changing_does_not_touch_snapshot(db):
    cid = _company(db)
    wo = _wo(db, cid)
    cat = TimeCategory(name="常规", hourly_rate=Decimal("100"), company_id=cid)
    db.add(cat)
    db.commit()
    row = labor.create_labor(
        db, wo, LaborCreate(duration_seconds=3600, time_category_id=cat.id), cid, actor_user_id=None
    )
    cat.hourly_rate = Decimal("999")
    db.commit()
    db.refresh(row)
    assert row.hourly_rate == Decimal("100")


def test_unknown_category_404(db):
    cid = _company(db)
    wo = _wo(db, cid)
    with pytest.raises(HTTPException) as e:
        labor.create_labor(
            db,
            wo,
            LaborCreate(duration_seconds=10, time_category_id="nope"),
            cid,
            actor_user_id=None,
        )
    assert e.value.status_code == 404


def test_timer_start_stop(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.start_timer(
        db, wo, LaborTimerStart(hourly_rate=Decimal("60")), cid, actor_user_id="u1"
    )
    assert row.started_at is not None and row.stopped_at is None
    assert labor.is_running(row) is True
    assert labor.compute_cost(row) == Decimal("0.00")
    from datetime import timedelta

    row.started_at = row.started_at - timedelta(hours=1)
    db.commit()
    stopped = labor.stop_timer(db, row)
    assert stopped.stopped_at is not None
    assert stopped.duration_seconds == pytest.approx(3600, abs=5)


def test_timer_double_start_conflict(db):
    cid = _company(db)
    wo = _wo(db, cid)
    labor.start_timer(db, wo, LaborTimerStart(user_id="u1"), cid, actor_user_id="u1")
    with pytest.raises(HTTPException) as e:
        labor.start_timer(db, wo, LaborTimerStart(user_id="u1"), cid, actor_user_id="u1")
    assert e.value.status_code == 409


def test_stop_non_running_400(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.create_labor(
        db,
        wo,
        LaborCreate(duration_seconds=600, hourly_rate=Decimal("10")),
        cid,
        actor_user_id=None,
    )
    with pytest.raises(HTTPException) as e:
        labor.stop_timer(db, row)
    assert e.value.status_code == 400


def test_update_and_delete(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.create_labor(
        db,
        wo,
        LaborCreate(duration_seconds=600, hourly_rate=Decimal("10")),
        cid,
        actor_user_id=None,
    )
    labor.update_labor(db, row, LaborUpdate(duration_seconds=1200, hourly_rate=Decimal("20")), cid)
    assert row.duration_seconds == 1200
    assert row.hourly_rate == Decimal("20")
    labor.delete_labor(db, row)
    assert labor.list_labor(db, wo.id) == []


def test_update_unknown_category_404(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.create_labor(
        db,
        wo,
        LaborCreate(duration_seconds=600, hourly_rate=Decimal("10")),
        cid,
        actor_user_id=None,
    )
    with pytest.raises(HTTPException) as e:
        labor.update_labor(db, row, LaborUpdate(time_category_id="nope"), cid)
    assert e.value.status_code == 404


def test_running_elapsed_seconds(db):
    cid = _company(db)
    wo = _wo(db, cid)
    # 运行中计时器：running_elapsed_seconds 应为非负整数
    row = labor.start_timer(
        db, wo, LaborTimerStart(hourly_rate=Decimal("60")), cid, actor_user_id="u2"
    )
    read = LaborRead.model_validate(row)
    assert read.running_elapsed_seconds is not None
    assert read.running_elapsed_seconds >= 0
    # 手填（非运行中）labor：running_elapsed_seconds 应为 None
    static_row = labor.create_labor(
        db,
        wo,
        LaborCreate(duration_seconds=3600, hourly_rate=Decimal("80")),
        cid,
        actor_user_id=None,
    )
    static_read = LaborRead.model_validate(static_row)
    assert static_read.running_elapsed_seconds is None
