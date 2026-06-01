from app.models.asset_status import DOWN_STATUSES, UP_STATUSES, AssetStatus
from app.models.company import Company
from app.models.maintenance_asset import Asset


def test_status_up_down_partition():
    all_values = set(AssetStatus)
    assert all_values == UP_STATUSES | DOWN_STATUSES
    assert set() == UP_STATUSES & DOWN_STATUSES
    assert AssetStatus.OPERATIONAL in UP_STATUSES
    assert AssetStatus.DOWN in DOWN_STATUSES
    assert AssetStatus.EMERGENCY_SHUTDOWN in DOWN_STATUSES


def test_asset_defaults(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    a = Asset(custom_id="A000001", name="泵1", company_id=c.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    assert a.status == AssetStatus.OPERATIONAL
    assert a.id is not None and len(a.id) == 36
