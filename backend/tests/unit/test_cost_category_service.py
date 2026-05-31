from sqlalchemy.orm import Session

from app.schemas.partner import CostCategoryCreate, CostCategoryUpdate
from app.services import cost_category_service as svc

CO = "co-1"


def test_create_and_get(db: Session):
    c = svc.create_cost_category(db, CostCategoryCreate(name="耗材"), CO, actor_user_id="a")
    assert c.id and svc.get_cost_category(db, c.id).name == "耗材"


def test_list(db: Session):
    svc.create_cost_category(db, CostCategoryCreate(name="A"), CO, actor_user_id="a")
    svc.create_cost_category(db, CostCategoryCreate(name="B"), CO, actor_user_id="a")
    assert len(svc.list_cost_categories(db)) == 2


def test_update(db: Session):
    c = svc.create_cost_category(db, CostCategoryCreate(name="旧"), CO, actor_user_id="a")
    svc.update_cost_category(db, c, CostCategoryUpdate(name="新", description="d"),
                             CO, actor_user_id="a")
    assert c.name == "新" and c.description == "d"


def test_delete_soft(db: Session):
    c = svc.create_cost_category(db, CostCategoryCreate(name="X"), CO, actor_user_id="a")
    svc.delete_cost_category(db, c)
    assert svc.get_cost_category(db, c.id) is None
