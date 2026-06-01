from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.part import (
    MultiPartCreate,
    MultiPartUpdate,
    PartCategoryCreate,
    PartConsumptionCreate,
    PartConsumptionRead,
    PartCreate,
    PartMini,
    PartUpdate,
)


def test_part_mini_fields():
    m = PartMini(id="p-1", name="轴承", custom_id="PRT000001")
    assert m.id == "p-1" and m.name == "轴承" and m.custom_id == "PRT000001"


def test_part_create_defaults():
    p = PartCreate(name="轴承")
    assert p.cost == Decimal("0") and p.quantity == Decimal("0")
    assert p.min_quantity == Decimal("0") and p.non_stock is False
    assert p.unit == "" and p.category_id is None
    assert p.assignee_ids == [] and p.team_ids == [] and p.asset_ids == []


def test_part_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        PartCreate(name="")


def test_part_update_all_optional():
    assert PartUpdate().model_dump(exclude_unset=True) == {}


def test_category_create():
    c = PartCategoryCreate(name="轴承类")
    assert c.name == "轴承类" and c.description == ""


def test_consumption_create_requires_fields():
    c = PartConsumptionCreate(part_id="p-1", quantity=Decimal("2"))
    assert c.quantity == Decimal("2")
    with pytest.raises(ValidationError):
        PartConsumptionCreate(part_id="p-1")


def test_consumption_read_total_cost():
    r = PartConsumptionRead(
        id="c-1",
        part_id="p-1",
        work_order_id="wo-1",
        quantity=Decimal("3"),
        unit_cost=Decimal("9.99"),
        consumed_by_user_id=None,
        consumed_at="2026-06-01T00:00:00",
    )
    assert r.total_cost == Decimal("29.97")


def test_multipart_create_and_update():
    m = MultiPartCreate(name="套件")
    assert m.part_ids == []
    assert MultiPartUpdate().model_dump(exclude_unset=True) == {}
