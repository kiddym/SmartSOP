import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260531_0008_phase3b_vendor")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "phase3b_vendor"
    assert m.down_revision == "phase3a_part"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_part (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_vendor",
                "tb_customer",
                "tb_cost_category",
                "tb_vendor_part",
                "tb_customer_part",
            } <= tables
            _mod().downgrade()
            assert "tb_vendor" not in inspect(conn).get_table_names()
