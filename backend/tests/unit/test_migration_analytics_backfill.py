"""迁移 analytics_backfill：链路 + up/down 可重放（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260602_0004_analytics_backfill")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "analytics_backfill"
    assert m.down_revision == "workorder_labor_cost"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql(
            "CREATE TABLE tb_work_order (id VARCHAR(36) PRIMARY KEY, title VARCHAR(300))"
        )
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            insp = inspect(conn)
            assert "tb_work_order_category" in insp.get_table_names()
            wo_cols = {c["name"] for c in insp.get_columns("tb_work_order")}
            assert {"category_id", "created_by_user_id"} <= wo_cols
            _mod().downgrade()
            insp2 = inspect(conn)
            assert "tb_work_order_category" not in insp2.get_table_names()
            wo_cols2 = {c["name"] for c in insp2.get_columns("tb_work_order")}
            assert "category_id" not in wo_cols2 and "created_by_user_id" not in wo_cols2
    eng.dispose()
