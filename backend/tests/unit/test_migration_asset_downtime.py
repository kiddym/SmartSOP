"""迁移 asset_downtime_propagation：链路 + up/down 可重放（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260602_0005_asset_downtime_propagation")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "asset_downtime_propagation"
    assert m.down_revision == "analytics_backfill"  # rebased at merge for linear chain


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE tb_asset (id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql(
            "CREATE TABLE tb_asset_downtime (id VARCHAR(36) PRIMARY KEY, asset_id VARCHAR(36))"
        )
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            cols = {c["name"] for c in inspect(conn).get_columns("tb_asset_downtime")}
            assert {"source_asset_id", "prior_status"} <= cols
            _mod().downgrade()
            cols2 = {c["name"] for c in inspect(conn).get_columns("tb_asset_downtime")}
            assert "source_asset_id" not in cols2 and "prior_status" not in cols2
