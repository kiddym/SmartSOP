from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.part_category import PartCategory
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.services.analytics import inventory_analytics as svc

CO = "co-1"


def _part(db, *, custom_id="PRT1", name="x", cost="0", quantity="0", min_quantity="0",
          non_stock=False, category_id=None, is_active=True):
    p = Part(custom_id=custom_id, name=name, cost=Decimal(cost), quantity=Decimal(quantity),
             min_quantity=Decimal(min_quantity), non_stock=non_stock,
             category_id=category_id, is_active=is_active, company_id=CO)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_total_value_excludes_non_stock_and_inactive(db: Session):
    _part(db, custom_id="A", cost="10", quantity="5")              # 50
    _part(db, custom_id="B", cost="100", quantity="2", non_stock=True)  # 排除
    _part(db, custom_id="C", cost="9", quantity="9", is_active=False)   # 排除
    r = svc.inventory_dashboard(db)
    assert r["total_inventory_value"] == Decimal("50")


def test_value_by_category(db: Session):
    cat = PartCategory(name="轴承类", company_id=CO)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    _part(db, custom_id="A", cost="10", quantity="2", category_id=cat.id)  # 20
    _part(db, custom_id="B", cost="5", quantity="2")                        # 无分类 ->10
    r = svc.inventory_dashboard(db)
    by_cat = {row["name"]: row["value"] for row in r["inventory_value_by_category"]}
    assert by_cat["轴承类"] == Decimal("20")
    assert by_cat[None] == Decimal("10")


def test_low_stock(db: Session):
    _part(db, custom_id="LOW", quantity="1", min_quantity="5")    # 低
    _part(db, custom_id="OK", quantity="5", min_quantity="5")     # 等于不算低
    _part(db, custom_id="NS", quantity="0", min_quantity="9", non_stock=True)  # non_stock 不算
    r = svc.inventory_dashboard(db)
    assert r["low_stock_count"] == 1
    item = r["low_stock_items"][0]
    assert item["custom_id"] == "LOW" and item["shortfall"] == Decimal("4")


def test_top_consumed_in_window(db: Session):
    p1 = _part(db, custom_id="P1")
    p2 = _part(db, custom_id="P2")
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime(2026, 1, 5), company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    db.add(PartConsumption(part_id=p1.id, work_order_id=wo.id, quantity=Decimal("2"),
                           unit_cost=Decimal("1"), consumed_at=datetime(2026, 1, 10), company_id=CO))
    db.add(PartConsumption(part_id=p2.id, work_order_id=wo.id, quantity=Decimal("7"),
                           unit_cost=Decimal("1"), consumed_at=datetime(2026, 1, 10), company_id=CO))
    db.commit()
    r = svc.inventory_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["top_consumed_parts"][0]["custom_id"] == "P2"   # 量大在前
    assert r["top_consumed_parts"][0]["qty"] == Decimal("7")
