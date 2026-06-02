"""迁移 workorder_labor_cost 的链路与 up/down 可重放性（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260602_0003_workorder_labor_cost")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "workorder_labor_cost"
    assert m.down_revision == "universal_attachment"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_user (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_work_order (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_cost_category (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_time_category",
                "tb_work_order_labor",
                "tb_work_order_additional_cost",
            } <= tables
            _mod().downgrade()
            remaining = set(inspect(conn).get_table_names())
            assert "tb_time_category" not in remaining
            assert "tb_work_order_labor" not in remaining
            assert "tb_work_order_additional_cost" not in remaining
    eng.dispose()
