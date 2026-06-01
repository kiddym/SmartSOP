from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.partner import CustomerCreate, CustomerUpdate
from app.services import customer_service as svc

CO = "co-1"


def test_create_customer_with_parts_and_currency(db: Session):
    c = svc.create_customer(
        db,
        CustomerCreate(
            name="客户A",
            customer_type="大客户",
            billing_currency="CNY",
            rate=Decimal("0"),
            part_ids=["p-2", "p-1"],
        ),
        CO,
        actor_user_id="a",
    )
    assert c.id and c.billing_currency == "CNY"
    assert svc.part_ids(db, c.id) == ["p-1", "p-2"]  # 按 part_id 序


def test_list_and_filter_by_part(db: Session):
    svc.create_customer(db, CustomerCreate(name="A", part_ids=["p-1"]), CO, actor_user_id="a")
    svc.create_customer(db, CustomerCreate(name="B", part_ids=["p-2"]), CO, actor_user_id="a")
    assert len(svc.list_customers(db)) == 2
    got = svc.list_customers(db, part_id="p-2")
    assert len(got) == 1 and got[0].name == "B"


def test_update_replaces_parts(db: Session):
    c = svc.create_customer(db, CustomerCreate(name="A", part_ids=["p-1"]), CO, actor_user_id="a")
    svc.update_customer(
        db, c, CustomerUpdate(billing_currency="USD", part_ids=["p-9"]), CO, actor_user_id="a"
    )
    assert c.billing_currency == "USD"
    assert svc.part_ids(db, c.id) == ["p-9"]


def test_delete_customer_soft(db: Session):
    c = svc.create_customer(db, CustomerCreate(name="A"), CO, actor_user_id="a")
    svc.delete_customer(db, c)
    assert svc.get_customer(db, c.id) is None
