"""迁移 workorder_2b_backfill：链路 + up/down 可重放（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260604_0001_workorder_2b_backfill")


def test_revision_chain():
    m = _mod()
    assert m.revision == "workorder_2b_backfill"
    assert m.down_revision == "inventory_backfill"


def test_upgrade_downgrade_sqlite():
    eng = create_engine("sqlite://")
    new_cols = {
        "completed_by_user_id",
        "feedback",
        "urgent",
        "estimated_duration",
        "estimated_start_date",
        "first_responded_at",
        "archived",
        "is_compliant",
    }
    with eng.begin() as conn:
        for tbl in ("tb_company", "tb_work_order"):
            conn.exec_driver_sql(f"CREATE TABLE {tbl} (id VARCHAR(36) PRIMARY KEY)")
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert "tb_work_order_relation" in tables
            cols = {c["name"] for c in inspect(conn).get_columns("tb_work_order")}
            assert new_cols <= cols
            _mod().downgrade()
            tables2 = set(inspect(conn).get_table_names())
            assert "tb_work_order_relation" not in tables2
            cols2 = {c["name"] for c in inspect(conn).get_columns("tb_work_order")}
            assert new_cols.isdisjoint(cols2)
    eng.dispose()
