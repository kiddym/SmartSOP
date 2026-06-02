"""迁移 inventory_backfill：链路 + up/down 可重放（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260602_0006_inventory_backfill")


def test_revision_chain():
    m = _mod()
    assert m.revision == "inventory_backfill"
    assert m.down_revision == "asset_downtime_propagation"  # rebased at merge for linear chain


def test_upgrade_downgrade_sqlite():
    eng = create_engine("sqlite://")
    parents = (
        "tb_company",
        "tb_part",
        "tb_location",
        "tb_asset",
        "tb_vendor",
        "tb_customer",
        "tb_preventive_maintenance",
        "tb_purchase_order",
    )
    with eng.begin() as conn:
        for tbl in parents:
            conn.exec_driver_sql(f"CREATE TABLE {tbl} (id VARCHAR(36) PRIMARY KEY)")
        new_tables = {
            "tb_part_location",
            "tb_part_pm",
            "tb_vendor_asset",
            "tb_vendor_location",
            "tb_customer_asset",
            "tb_customer_location",
            "tb_purchase_order_category",
        }
        new_po_cols = {
            "category_id",
            "shipping_address",
            "shipping_method",
            "terms_of_payment",
            "expected_delivery_date",
        }
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert new_tables <= tables
            po_cols = {c["name"] for c in inspect(conn).get_columns("tb_purchase_order")}
            assert new_po_cols <= po_cols
            _mod().downgrade()
            # down 须镜像 up：所有新建表与 PO 新列全部消失（不只抽查一张）
            tables2 = set(inspect(conn).get_table_names())
            assert new_tables.isdisjoint(tables2)
            po_cols2 = {c["name"] for c in inspect(conn).get_columns("tb_purchase_order")}
            assert new_po_cols.isdisjoint(po_cols2)
    eng.dispose()
