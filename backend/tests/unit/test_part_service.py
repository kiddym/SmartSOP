from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.part import PartCreate, PartUpdate
from app.services import part_service as svc

CO = "co-1"


def test_create_part_assigns_custom_id_and_relations(db: Session):
    p = svc.create_part(
        db,
        PartCreate(
            name="轴承",
            cost=Decimal("12.5"),
            quantity=Decimal("10"),
            min_quantity=Decimal("3"),
            unit="pcs",
            assignee_ids=["u-1", "u-2"],
            team_ids=["t-1"],
            asset_ids=["as-1"],
        ),
        CO,
        actor_user_id="a",
    )
    assert p.custom_id == "PRT000001"
    assert set(svc.assignee_ids(db, p.id)) == {"u-1", "u-2"}
    assert svc.team_ids(db, p.id) == ["t-1"]
    assert svc.asset_ids(db, p.id) == ["as-1"]


def test_list_and_filter_parts(db: Session):
    svc.create_part(
        db,
        PartCreate(name="A", asset_ids=["as-1"], quantity=Decimal("1"), min_quantity=Decimal("5")),
        CO,
        actor_user_id="a",
    )
    svc.create_part(
        db,
        PartCreate(name="B", quantity=Decimal("9"), min_quantity=Decimal("5")),
        CO,
        actor_user_id="a",
    )
    assert len(svc.list_parts(db)) == 2
    assert len(svc.list_parts(db, asset_id="as-1")) == 1
    low = svc.list_parts(db, low_stock=True)
    assert len(low) == 1 and low[0].name == "A"  # 1 < 5


def test_filter_by_category(db: Session):
    from app.schemas.part import PartCategoryCreate
    from app.services import part_category_service as cs

    cat = cs.create_category(db, PartCategoryCreate(name="轴承类"), CO, actor_user_id="a")
    svc.create_part(db, PartCreate(name="A", category_id=cat.id), CO, actor_user_id="a")
    svc.create_part(db, PartCreate(name="B"), CO, actor_user_id="a")
    got = svc.list_parts(db, category_id=cat.id)
    assert len(got) == 1 and got[0].name == "A"


def test_update_part_quantity_and_relations(db: Session):
    p = svc.create_part(db, PartCreate(name="轴承", assignee_ids=["u-1"]), CO, actor_user_id="a")
    svc.update_part(
        db, p, PartUpdate(quantity=Decimal("99"), assignee_ids=["u-9"]), CO, actor_user_id="a"
    )
    assert p.quantity == Decimal("99")
    assert svc.assignee_ids(db, p.id) == ["u-9"]  # 全量替换


def test_delete_part_soft(db: Session):
    p = svc.create_part(db, PartCreate(name="轴承"), CO, actor_user_id="a")
    svc.delete_part(db, p)
    assert svc.get_part(db, p.id) is None
