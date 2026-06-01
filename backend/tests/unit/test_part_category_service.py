from sqlalchemy.orm import Session

from app.schemas.part import PartCategoryCreate, PartCategoryUpdate
from app.services import part_category_service as svc

CO = "co-1"


def test_create_and_get_category(db: Session):
    c = svc.create_category(db, PartCategoryCreate(name="轴承类"), CO, actor_user_id="a")
    assert c.id and svc.get_category(db, c.id).name == "轴承类"


def test_list_categories(db: Session):
    svc.create_category(db, PartCategoryCreate(name="A"), CO, actor_user_id="a")
    svc.create_category(db, PartCategoryCreate(name="B"), CO, actor_user_id="a")
    assert len(svc.list_categories(db)) == 2


def test_update_category(db: Session):
    c = svc.create_category(db, PartCategoryCreate(name="旧"), CO, actor_user_id="a")
    svc.update_category(
        db, c, PartCategoryUpdate(name="新", description="d"), CO, actor_user_id="a"
    )
    assert c.name == "新" and c.description == "d"


def test_delete_category_soft(db: Session):
    c = svc.create_category(db, PartCategoryCreate(name="X"), CO, actor_user_id="a")
    svc.delete_category(db, c)
    assert svc.get_category(db, c.id) is None
