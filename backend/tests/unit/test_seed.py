"""seed 单测（data-model §6）。"""

from __future__ import annotations

from app import seed
from app.models.field import ProcedureField
from app.models.folder import Folder, FolderSequence
from app.models.settings import ProcedureSettings


def test_run_seed_creates_system_folders(db) -> None:
    seed.run_seed(db)

    deprecated = db.query(Folder).filter_by(name=seed.DEPRECATED_FOLDER_NAME).one()
    archived = db.query(Folder).filter_by(name=seed.ARCHIVED_FOLDER_NAME).one()

    assert deprecated.system is True
    assert deprecated.parent_id is None
    assert archived.system is True
    assert archived.parent_id is None


def test_run_seed_creates_settings_singleton(db) -> None:
    seed.run_seed(db)
    assert db.query(ProcedureSettings).count() == 1


def test_run_seed_creates_sample_field(db) -> None:
    seed.run_seed(db)
    field = db.query(ProcedureField).one()
    assert field.field_type == "select"
    assert field.key == field.key.lower()


def test_run_seed_is_idempotent(db) -> None:
    """重复运行不重复插入（data-model §6 幂等）。"""
    seed.run_seed(db)
    seed.run_seed(db)
    seed.run_seed(db)

    assert db.query(Folder).filter_by(system=True).count() == 2  # 废止 + 归档
    assert db.query(ProcedureSettings).count() == 1
    assert db.query(ProcedureField).count() == 1
    assert db.query(FolderSequence).count() == 0
