from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.purchase_order import (
    POLineCreate,
    POLineRead,
    POResolve,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)


def test_create_defaults():
    po = PurchaseOrderCreate(vendor_id="v-1")
    assert po.notes == "" and po.lines == []


def test_create_rejects_blank_vendor():
    with pytest.raises(ValidationError):
        PurchaseOrderCreate(vendor_id="")


def test_line_create_and_default_cost():
    ln = POLineCreate(part_id="p-1", quantity=Decimal("3"))
    assert ln.unit_cost == Decimal("0")


def test_line_read_line_total_computed():
    lr = POLineRead(id="l-1", part_id="p-1", quantity=Decimal("3"), unit_cost=Decimal("2.5"))
    assert lr.line_total == Decimal("7.5")
    assert lr.model_dump()["line_total"] == Decimal("7.5")


def test_update_all_optional():
    assert PurchaseOrderUpdate().model_dump(exclude_unset=True) == {}


def test_resolve_default_note():
    assert POResolve().note == ""
