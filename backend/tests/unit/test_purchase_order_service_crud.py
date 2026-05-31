from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.purchase_order_status import PurchaseOrderStatus
from app.schemas.purchase_order import (
    POLineCreate,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)
from app.services import purchase_order_service as svc

CO = "co-1"


def _payload(**kw):
    kw.setdefault("vendor_id", "v-1")
    return PurchaseOrderCreate(**kw)


def test_create_assigns_custom_id_and_lines(db: Session):
    po = svc.create_purchase_order(db, _payload(lines=[
        POLineCreate(part_id="p-1", quantity=Decimal("3"), unit_cost=Decimal("2")),
        POLineCreate(part_id="p-2", quantity=Decimal("1")),
    ]), CO, actor_user_id="a")
    assert po.custom_id.startswith("PO") and po.status == PurchaseOrderStatus.DRAFT
    assert [ln.part_id for ln in svc.lines(db, po.id)] == ["p-1", "p-2"]


def test_list_and_filters(db: Session):
    svc.create_purchase_order(db, _payload(vendor_id="v-1"), CO, actor_user_id="a")
    svc.create_purchase_order(db, _payload(vendor_id="v-2"), CO, actor_user_id="a")
    assert len(svc.list_purchase_orders(db)) == 2
    got = svc.list_purchase_orders(db, vendor_id="v-2")
    assert len(got) == 1 and got[0].vendor_id == "v-2"
    drafts = svc.list_purchase_orders(db, status="DRAFT")
    assert len(drafts) == 2


def test_get_soft_deleted_hidden(db: Session):
    po = svc.create_purchase_order(db, _payload(), CO, actor_user_id="a")
    svc.delete_purchase_order(db, po)
    assert svc.get_purchase_order(db, po.id) is None


def test_update_draft_replaces_lines_and_scalars(db: Session):
    po = svc.create_purchase_order(db, _payload(notes="old", lines=[
        POLineCreate(part_id="p-1", quantity=Decimal("1"))]), CO, actor_user_id="a")
    svc.update_purchase_order(db, po, PurchaseOrderUpdate(notes="new", lines=[
        POLineCreate(part_id="p-9", quantity=Decimal("2"), unit_cost=Decimal("4"))]),
        CO, actor_user_id="a")
    assert po.notes == "new"
    lines = svc.lines(db, po.id)
    assert len(lines) == 1 and lines[0].part_id == "p-9"


def test_update_keeps_lines_when_omitted(db: Session):
    po = svc.create_purchase_order(db, _payload(lines=[
        POLineCreate(part_id="p-1", quantity=Decimal("1"))]), CO, actor_user_id="a")
    svc.update_purchase_order(db, po, PurchaseOrderUpdate(notes="x"), CO, actor_user_id="a")
    assert len(svc.lines(db, po.id)) == 1
