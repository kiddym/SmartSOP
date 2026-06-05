from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.config import settings

_ROOT = Path(__file__).resolve().parent.parent.parent


def _cfg() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    return cfg


def test_single_head_is_p6_stripe_billing() -> None:
    assert ScriptDirectory.from_config(_cfg()).get_heads() == ["p6_stripe_billing"]


def test_sqlite_upgrade_downgrade_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "rt.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    cfg = _cfg()
    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db_path)
    try:
        company_cols = {r[1] for r in conn.execute("PRAGMA table_info(tb_company)")}
        assert {"stripe_customer_id", "stripe_subscription_id"} <= company_cols
        event_cols = {r[1] for r in conn.execute("PRAGMA table_info(tb_billing_event)")}
        assert event_cols == {"event_id", "event_type", "processed_at"}
    finally:
        conn.close()
    command.downgrade(cfg, "-1")
    command.upgrade(cfg, "head")
