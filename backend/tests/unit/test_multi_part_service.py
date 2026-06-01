from sqlalchemy.orm import Session

from app.schemas.part import MultiPartCreate, MultiPartUpdate
from app.services import multi_part_service as svc

CO = "co-1"


def test_create_multipart_assigns_custom_id_and_items(db: Session):
    m = svc.create_multi_part(
        db, MultiPartCreate(name="保养套件", part_ids=["p-1", "p-2"]), CO, actor_user_id="a"
    )
    assert m.custom_id == "KIT000001"
    assert svc.part_ids(db, m.id) == ["p-1", "p-2"]


def test_list_multiparts(db: Session):
    svc.create_multi_part(db, MultiPartCreate(name="A"), CO, actor_user_id="a")
    svc.create_multi_part(db, MultiPartCreate(name="B"), CO, actor_user_id="a")
    assert len(svc.list_multi_parts(db)) == 2


def test_update_replaces_items(db: Session):
    m = svc.create_multi_part(
        db, MultiPartCreate(name="套件", part_ids=["p-1"]), CO, actor_user_id="a"
    )
    svc.update_multi_part(
        db, m, MultiPartUpdate(name="改名", part_ids=["p-9", "p-8"]), CO, actor_user_id="a"
    )
    assert m.name == "改名"
    assert svc.part_ids(db, m.id) == ["p-8", "p-9"]  # 全量替换（按 part_id 序）


def test_delete_multipart_soft(db: Session):
    m = svc.create_multi_part(db, MultiPartCreate(name="X"), CO, actor_user_id="a")
    svc.delete_multi_part(db, m)
    assert svc.get_multi_part(db, m.id) is None
