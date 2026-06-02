"""AssetDowntime 新列 source_asset_id / prior_status 存在且可读写。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.asset_downtime import AssetDowntime
from app.models.company import Company


def test_new_columns_roundtrip(db):
    co = Company(name="Acme", slug="acme")
    db.add(co)
    db.flush()
    dt = AssetDowntime(
        asset_id="a1", started_at=datetime.utcnow(), downtime_type="cascade",
        source_asset_id="parent-1", prior_status="STANDBY", company_id=co.id,
    )
    db.add(dt)
    db.commit()
    row = db.execute(select(AssetDowntime)).scalar_one()
    assert row.source_asset_id == "parent-1"
    assert row.prior_status == "STANDBY"
