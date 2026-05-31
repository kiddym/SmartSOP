import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260531_0005_phase2b_pm")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "phase2b_pm"
    assert m.down_revision == "phase2a_request"


def test_upgrade_then_downgrade_sqlite():
    # 先建 PM 依赖的父表骨架，再在同一连接上跑本迁移 upgrade/downgrade。
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_asset (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_location (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_user (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_team (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        # alembic 1.18: Operations.context() 接收 MigrationContext 本身。
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_preventive_maintenance", "tb_pm_assignee",
                "tb_pm_team", "tb_pm_activity",
            } <= tables
            _mod().downgrade()
            assert "tb_preventive_maintenance" not in inspect(conn).get_table_names()
