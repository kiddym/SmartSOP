import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260531_0006_phase2c_meter")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "phase2c_meter"
    assert m.down_revision == "phase2b_pm"


def test_upgrade_then_downgrade_sqlite():
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
                "tb_meter",
                "tb_meter_reading",
                "tb_meter_trigger",
                "tb_meter_trigger_assignee",
                "tb_meter_trigger_team",
            } <= tables
            _mod().downgrade()
            assert "tb_meter" not in inspect(conn).get_table_names()
