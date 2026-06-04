"""sop_tenancy_hardening 迁移：单 head + SQLite upgrade/downgrade 往返。

测试库平时走 Base.metadata.create_all（不走 alembic），本测试单独在全新 SQLite 文件库
上真实跑 alembic，验证迁移本身可正向/反向执行、且 upgrade 后 company_id 收 NOT NULL。
MySQL 集成（生成列 / partial-unique）仅手验，列为遗留。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.config import settings

_ROOT = Path(__file__).resolve().parent.parent


def _alembic_cfg() -> Config:
    # 不传 alembic.ini：否则 env.py 的 fileConfig() 会按 ini 的 [logging] 重配全局
    # logging（disable_existing_loggers），污染后续断言 warning 的测试。仅显式设
    # script_location；DB url 由 env.py 读 settings.database_url。
    cfg = Config()
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    return cfg


def test_single_head_is_sop_tenancy_hardening() -> None:
    heads = ScriptDirectory.from_config(_alembic_cfg()).get_heads()
    assert heads == ["sop_tenancy_hardening"]


def test_migration_module_importable_with_revisions() -> None:
    import importlib

    m = importlib.import_module("alembic.versions.20260604_0003_sop_tenancy_hardening")
    assert m.revision == "sop_tenancy_hardening"
    assert m.down_revision == "p6_commercialization_gating"
    assert hasattr(m, "upgrade") and hasattr(m, "downgrade")


def test_sqlite_upgrade_downgrade_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """全新 SQLite 库 upgrade head → downgrade -1 → 再 upgrade head；末态 company_id NOT NULL。"""
    db_path = tmp_path / "roundtrip.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")  # env.py 读取此值
    cfg = _alembic_cfg()

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")  # sop_tenancy_hardening → p6_commercialization_gating
    command.upgrade(cfg, "head")

    conn = sqlite3.connect(db_path)
    try:
        for table in (
            "tb_procedure_field",
            "tb_procedure_asset",
            "tb_folder",
            "tb_procedure",
            "tb_attachment",
            "tb_procedure_audit_log",
        ):
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            company = next(c for c in cols if c[1] == "company_id")
            assert company[3] == 1, f"{table}.company_id 应 NOT NULL"
        # 复合唯一就位（company_id 在内）
        fld = conn.execute("PRAGMA index_list(tb_procedure_field)").fetchall()
        composite = [
            [r[2] for r in conn.execute(f"PRAGMA index_info({i[1]})").fetchall()]
            for i in fld
            if i[2]
        ]
        assert ["company_id", "key"] in composite
    finally:
        conn.close()
