from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.multi_part import MultiPart, MultiPartItem
from app.models.part import Part, PartAsset, PartAssignee, PartTeam
from app.models.part_category import PartCategory
from app.models.part_consumption import PartConsumption


def test_part_row_and_low_stock(db: Session):
    cat = PartCategory(name="轴承", company_id="co-1")
    db.add(cat)
    db.commit()
    db.refresh(cat)
    p = Part(
        custom_id="PRT000001",
        name="6204 轴承",
        cost=Decimal("12.5000"),
        quantity=Decimal("3.0000"),
        min_quantity=Decimal("5.0000"),
        unit="pcs",
        category_id=cat.id,
        company_id="co-1",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    assert p.id and p.is_active is True and p.non_stock is False
    assert p.is_low_stock is True  # 3 < 5 且计库存
    p.quantity = Decimal("10.0000")
    assert p.is_low_stock is False  # 10 >= 5
    p.non_stock = True
    p.quantity = Decimal("0.0000")
    assert p.is_low_stock is False  # non_stock 永不低库存
    db.add(PartAssignee(part_id=p.id, user_id="u-1", company_id="co-1"))
    db.add(PartTeam(part_id=p.id, team_id="t-1", company_id="co-1"))
    db.add(PartAsset(part_id=p.id, asset_id="as-1", company_id="co-1"))
    db.commit()


def test_consumption_and_multipart(db: Session):
    p = Part(custom_id="PRT000002", name="滤芯", company_id="co-1")
    db.add(p)
    db.commit()
    db.refresh(p)
    db.add(
        PartConsumption(
            part_id=p.id,
            work_order_id="wo-1",
            quantity=Decimal("2.0000"),
            unit_cost=Decimal("9.9900"),
            company_id="co-1",
        )
    )
    mp = MultiPart(custom_id="KIT000001", name="保养套件", company_id="co-1")
    db.add(mp)
    db.commit()
    db.refresh(mp)
    db.add(MultiPartItem(multi_part_id=mp.id, part_id=p.id, company_id="co-1"))
    db.commit()
    c = db.query(PartConsumption).filter_by(part_id=p.id).one()
    assert c.consumed_at is not None  # default utcnow


def test_part_exports_registered():
    import app.models as mod

    for name in (
        "Part",
        "PartAssignee",
        "PartTeam",
        "PartAsset",
        "PartCategory",
        "PartConsumption",
        "MultiPart",
        "MultiPartItem",
    ):
        assert name in mod.__all__ and hasattr(mod, name)
