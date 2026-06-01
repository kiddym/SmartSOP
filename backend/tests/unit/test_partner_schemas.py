from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.partner import (
    CostCategoryCreate,
    CustomerCreate,
    CustomerUpdate,
    VendorCreate,
    VendorMini,
    VendorUpdate,
)


def test_vendor_create_defaults():
    v = VendorCreate(name="供应商A")
    assert v.vendor_type == "" and v.description == "" and v.rate == Decimal("0")
    assert v.address == "" and v.phone == "" and v.email == "" and v.website == ""
    assert v.part_ids == []


def test_vendor_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        VendorCreate(name="")


def test_vendor_update_all_optional():
    assert VendorUpdate().model_dump(exclude_unset=True) == {}


def test_vendor_mini_fields():
    m = VendorMini(id="v-1", name="供应商A")
    assert m.id == "v-1" and m.name == "供应商A"


def test_customer_create_defaults_and_currency():
    c = CustomerCreate(name="客户A", billing_currency="CNY")
    assert c.billing_currency == "CNY" and c.customer_type == ""
    assert c.rate == Decimal("0") and c.part_ids == []


def test_customer_update_all_optional():
    assert CustomerUpdate().model_dump(exclude_unset=True) == {}


def test_cost_category_create():
    cc = CostCategoryCreate(name="耗材")
    assert cc.name == "耗材" and cc.description == ""
