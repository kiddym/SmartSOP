from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset
from app.services.analytics import asset_reliability_analytics as svc

CO = "co-1"


def _asset(db, custom_id="AST1", name="pump", location_id=None, category_id=None):
    a = Asset(custom_id=custom_id, name=name, location_id=location_id,
              category_id=category_id, company_id=CO)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _down(db, asset, started_at, ended_at=None):
    db.add(AssetDowntime(asset_id=asset.id, started_at=started_at, ended_at=ended_at,
                         company_id=CO))
    db.commit()


def test_no_downtime_full_availability(db: Session):
    _asset(db)
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    assert r["window_hours"] == 24.0
    row = r["assets"][0]
    assert row["availability_pct"] == 100.0 and row["downtime_count"] == 0
    assert row["mttr_hours"] is None and row["mtbf_hours"] is None


def test_downtime_availability_mttr_mtbf(db: Session):
    a = _asset(db)
    # 窗口 1/1 00:00 .. 1/2 00:00（24h）。停机 6h。
    _down(db, a, datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 6))
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    row = r["assets"][0]
    assert row["total_downtime_hours"] == 6.0
    assert row["availability_pct"] == 75.0          # (24-6)/24
    assert row["mttr_hours"] == 6.0
    assert row["mtbf_hours"] == 18.0                # uptime 18 / 1 次


def test_ongoing_downtime_clipped_to_window_end(db: Session):
    a = _asset(db)
    _down(db, a, datetime(2026, 1, 1, 12), None)    # 进行中 -> 裁到 1/2 00:00 = 12h
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    row = r["assets"][0]
    assert row["total_downtime_hours"] == 12.0
    assert row["mttr_hours"] is None                # 进行中区间不计入 MTTR


def test_filter_by_location(db: Session):
    _asset(db, custom_id="A1", location_id="loc-1")
    _asset(db, custom_id="A2", location_id="loc-2")
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1),
                                        location_id="loc-1")
    assert {row["custom_id"] for row in r["assets"]} == {"A1"}


def test_fleet_rollup(db: Session):
    a1 = _asset(db, custom_id="A1")
    a2 = _asset(db, custom_id="A2")
    _down(db, a1, datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 6))
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    assert r["fleet_total_downtime_hours"] == 6.0
    assert r["fleet_availability_pct"] == 87.5      # (75 + 100)/2
