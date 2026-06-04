"""env-gated MySQL bootstrap：全新 MySQL 库 alembic upgrade head 整链成功。

平时测试库走 SQLite ``Base.metadata.create_all``，从不在 MySQL 上跑迁移链——历史上
整条链在第一个迁移即因 TEXT/JSON 字面 ``server_default``（MySQL 1101）失败，这正是
长期"MySQL 仅手验"遗留的根因。本测试把那条"MySQL 能不能 bootstrap"的红线变成可在
CI 复跑的断言：仅当设置 ``TEST_MYSQL_URL`` 指向一个可清空的 MySQL 库时运行，缺省 skip
（无 MySQL 的 CI 不挂）。

用法：
    TEST_MYSQL_URL="mysql+pymysql://root@127.0.0.1:3306/sop_mysql_verify" \\
        .venv/bin/python -m pytest tests/test_mysql_bootstrap.py -q
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from alembic import command
from app.config import settings

_ROOT = Path(__file__).resolve().parent.parent
_MYSQL_URL = os.environ.get("TEST_MYSQL_URL")

pytestmark = pytest.mark.skipif(
    not _MYSQL_URL,
    reason="设置 TEST_MYSQL_URL（指向可清空的 MySQL 库）以运行 MySQL bootstrap 集成测试",
)


def _alembic_cfg() -> Config:
    # 与 test_migration_roundtrip 一致：不传 alembic.ini（避免 fileConfig 重配 logging），
    # 仅设 script_location；DB url 由 env.py 读 settings.database_url。
    cfg = Config()
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    return cfg


def _drop_all_tables(url: str) -> None:
    """清空目标库所有表，得到全新 bootstrap 起点（关 FK 检查避免删序依赖）。"""
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            tables = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = DATABASE()"
                    )
                )
            ]
            for t in tables:
                conn.execute(text(f"DROP TABLE IF EXISTS `{t}`"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    finally:
        engine.dispose()


def test_mysql_upgrade_head_full_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """全新 MySQL 库 alembic upgrade head 整链成功，末态停在单 head。"""
    assert _MYSQL_URL is not None  # skipif 已保证
    _drop_all_tables(_MYSQL_URL)
    monkeypatch.setattr(settings, "database_url", _MYSQL_URL)  # env.py 读取此值
    cfg = _alembic_cfg()

    # 整链 upgrade —— 历史首障是 initial_schema 的 TEXT 字面默认（1101），整链通即红线绿。
    command.upgrade(cfg, "head")

    # 单 head 守护：脚本目录仍单 head，且库已推进到该 head。
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert heads == ["sop_tenancy_hardening"]

    engine = create_engine(_MYSQL_URL)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == "sop_tenancy_hardening"
    finally:
        engine.dispose()
