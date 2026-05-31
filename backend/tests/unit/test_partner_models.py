from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.vendor import Vendor, VendorPart
from app.models.customer import Customer, CustomerPart
from app.models.cost_category import CostCategory


def test_vendor_row_and_parts(db: Session):
    v = Vendor(name="泉州轴承厂", vendor_type="轴承", rate=Decimal("8.5000"),
               email="a@b.com", company_id="co-1")
    db.add(v)
    db.commit()
    db.refresh(v)
    assert v.id and v.is_active is True
    assert v.vendor_type == "轴承" and v.description == "" and v.website == ""
    db.add(VendorPart(vendor_id=v.id, part_id="p-1", company_id="co-1"))
    db.commit()
    rel = db.query(VendorPart).filter_by(vendor_id=v.id).one()
    assert rel.part_id == "p-1"


def test_customer_row_and_parts(db: Session):
    c = Customer(name="某矿业", customer_type="大客户", rate=Decimal("0"),
                 billing_currency="CNY", company_id="co-1")
    db.add(c)
    db.commit()
    db.refresh(c)
    assert c.id and c.is_active is True and c.billing_currency == "CNY"
    assert c.description == "" and c.phone == ""
    db.add(CustomerPart(customer_id=c.id, part_id="p-1", company_id="co-1"))
    db.commit()
    rel = db.query(CustomerPart).filter_by(customer_id=c.id).one()
    assert rel.part_id == "p-1"


def test_cost_category_row(db: Session):
    cc = CostCategory(name="耗材", company_id="co-1")
    db.add(cc)
    db.commit()
    db.refresh(cc)
    assert cc.id and cc.is_active is True and cc.description == ""


def test_partner_exports_registered():
    import app.models as mod
    for name in ("Vendor", "VendorPart", "Customer", "CustomerPart", "CostCategory"):
        assert name in mod.__all__ and hasattr(mod, name)
