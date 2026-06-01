from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.schemas.part import PartCreate
from app.services import part_consumption_service as cs
from app.services import part_service as ps

CO = "co-1"


def _wo(db):
    wo = WorkOrder(custom_id="WO000001", title="检修", company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_consume_decrements_stock_and_snapshots_cost(db: Session):
    wo = _wo(db)
    p = ps.create_part(
        db,
        PartCreate(name="轴承", cost=Decimal("12.5"), quantity=Decimal("10")),
        CO,
        actor_user_id="a",
    )
    c = cs.consume_part(db, wo, p, Decimal("3"), CO, actor_user_id="u-1")
    assert isinstance(c, PartConsumption)
    assert c.unit_cost == Decimal("12.5") and c.quantity == Decimal("3")
    assert c.work_order_id == wo.id and c.consumed_by_user_id == "u-1"
    db.refresh(p)
    assert p.quantity == Decimal("7")  # 10 - 3


def test_consume_insufficient_raises(db: Session):
    wo = _wo(db)
    p = ps.create_part(db, PartCreate(name="轴承", quantity=Decimal("2")), CO, actor_user_id="a")
    with pytest.raises(HTTPException) as ei:
        cs.consume_part(db, wo, p, Decimal("5"), CO, actor_user_id="u-1")
    assert ei.value.status_code == 400
    db.refresh(p)
    assert p.quantity == Decimal("2")  # 未扣减


def test_consume_bad_quantity_raises(db: Session):
    wo = _wo(db)
    p = ps.create_part(db, PartCreate(name="轴承", quantity=Decimal("10")), CO, actor_user_id="a")
    with pytest.raises(HTTPException) as ei:
        cs.consume_part(db, wo, p, Decimal("0"), CO, actor_user_id="u-1")
    assert ei.value.status_code == 400


def test_consume_non_stock_records_but_no_decrement(db: Session):
    wo = _wo(db)
    p = ps.create_part(
        db,
        PartCreate(name="耗材", cost=Decimal("1.0"), quantity=Decimal("0"), non_stock=True),
        CO,
        actor_user_id="a",
    )
    c = cs.consume_part(db, wo, p, Decimal("100"), CO, actor_user_id="u-1")
    assert c.quantity == Decimal("100")  # 入台账
    db.refresh(p)
    assert p.quantity == Decimal("0")  # non_stock 不扣减、不报错


def test_list_consumptions_by_wo(db: Session):
    wo = _wo(db)
    p = ps.create_part(db, PartCreate(name="轴承", quantity=Decimal("10")), CO, actor_user_id="a")
    cs.consume_part(db, wo, p, Decimal("1"), CO, actor_user_id="u-1")
    cs.consume_part(db, wo, p, Decimal("2"), CO, actor_user_id="u-1")
    assert len(cs.list_consumptions(db, wo.id)) == 2
