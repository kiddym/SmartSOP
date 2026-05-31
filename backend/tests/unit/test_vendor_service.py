from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.partner import VendorCreate, VendorUpdate
from app.services import vendor_service as svc

CO = "co-1"


def test_create_vendor_with_parts(db: Session):
    v = svc.create_vendor(db, VendorCreate(
        name="供应商A", vendor_type="轴承", rate=Decimal("8.5"),
        part_ids=["p-1", "p-2", "p-1"]), CO, actor_user_id="a")
    assert v.id and v.vendor_type == "轴承"
    assert svc.part_ids(db, v.id) == ["p-1", "p-2"]          # 去重 + 按 part_id 序


def test_list_and_filter_by_part(db: Session):
    svc.create_vendor(db, VendorCreate(name="A", part_ids=["p-1"]), CO, actor_user_id="a")
    svc.create_vendor(db, VendorCreate(name="B", part_ids=["p-2"]), CO, actor_user_id="a")
    assert len(svc.list_vendors(db)) == 2
    got = svc.list_vendors(db, part_id="p-1")
    assert len(got) == 1 and got[0].name == "A"


def test_update_replaces_parts_and_scalars(db: Session):
    v = svc.create_vendor(db, VendorCreate(name="A", part_ids=["p-1"]), CO, actor_user_id="a")
    svc.update_vendor(db, v, VendorUpdate(name="改名", part_ids=["p-9", "p-8"]),
                      CO, actor_user_id="a")
    assert v.name == "改名"
    assert svc.part_ids(db, v.id) == ["p-8", "p-9"]          # 全量替换


def test_delete_vendor_soft(db: Session):
    v = svc.create_vendor(db, VendorCreate(name="A"), CO, actor_user_id="a")
    svc.delete_vendor(db, v)
    assert svc.get_vendor(db, v.id) is None
