import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260531_0007_phase3a_part")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "phase3a_part"
    assert m.down_revision == "phase2c_meter"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_work_order (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_asset (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_user (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_team (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_part",
                "tb_part_category",
                "tb_part_consumption",
                "tb_multi_part",
                "tb_multi_part_item",
                "tb_part_assignee",
                "tb_part_team",
                "tb_part_asset",
            } <= tables
            _mod().downgrade()
            assert "tb_part" not in inspect(conn).get_table_names()
