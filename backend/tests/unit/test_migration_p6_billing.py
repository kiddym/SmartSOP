"""P6 迁移：backfill 存量公司 plan/status + server_default。"""

import importlib

MOD = "alembic.versions.20260604_0002_p6_commercialization_gating"


def test_migration_module_importable_with_revisions():
    m = importlib.import_module(MOD)
    assert m.revision == "p6_commercialization_gating"
    assert m.down_revision == "workorder_2b_backfill"
    assert hasattr(m, "upgrade") and hasattr(m, "downgrade")
