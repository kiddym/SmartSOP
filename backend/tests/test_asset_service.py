import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.schemas.asset import AssetCreate, AssetUpdate
from app.services import maintenance_asset_service as svc


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def _ctx(db, company_id):
    tenant.set_current_company_id(company_id)


def test_create_assigns_custom_id_and_defaults(db):
    c = _company(db, "acme")
    _ctx(db, c.id)
    a = svc.create_asset(db, AssetCreate(name="泵1"), c.id)
    b = svc.create_asset(db, AssetCreate(name="泵2"), c.id)
    assert a.custom_id == "A000001"
    assert b.custom_id == "A000002"


def test_barcode_unique_within_tenant(db):
    c = _company(db, "acme")
    _ctx(db, c.id)
    svc.create_asset(db, AssetCreate(name="泵1", barcode="BC-1"), c.id)
    with pytest.raises(HTTPException) as exc:
        svc.create_asset(db, AssetCreate(name="泵2", barcode="BC-1"), c.id)
    assert exc.value.status_code == 409


def test_same_barcode_across_tenants_ok(db):
    c1 = _company(db, "acme"); c2 = _company(db, "globex")
    _ctx(db, c1.id)
    svc.create_asset(db, AssetCreate(name="泵", barcode="BC-1"), c1.id)
    _ctx(db, c2.id)
    svc.create_asset(db, AssetCreate(name="泵", barcode="BC-1"), c2.id)


def test_get_by_barcode_and_nfc(db):
    c = _company(db, "acme")
    _ctx(db, c.id)
    a = svc.create_asset(db, AssetCreate(name="泵", barcode="BC-9", nfc_id="NFC-9"), c.id)
    assert svc.get_by_barcode(db, "BC-9").id == a.id
    assert svc.get_by_nfc(db, "NFC-9").id == a.id
    assert svc.get_by_barcode(db, "nope") is None


def test_cycle_guard(db):
    c = _company(db, "acme")
    _ctx(db, c.id)
    root = svc.create_asset(db, AssetCreate(name="根"), c.id)
    child = svc.create_asset(db, AssetCreate(name="子", parent_id=root.id), c.id)
    with pytest.raises(HTTPException) as exc:
        svc.update_asset(db, root, AssetUpdate(parent_id=child.id), c.id)
    assert exc.value.status_code == 400


def test_relations_and_filters(db):
    from app.models.user import User
    c = _company(db, "acme")
    _ctx(db, c.id)
    u = User(company_id=c.id, email="w@a.com", password_hash="x", name="W")
    db.add(u); db.commit()
    a = svc.create_asset(db, AssetCreate(name="泵", assigned_user_ids=[u.id]), c.id)
    assert svc.assigned_user_ids(db, a.id) == [u.id]
    rows = svc.list_assets(db, status="OPERATIONAL")
    assert any(x.id == a.id for x in rows)
