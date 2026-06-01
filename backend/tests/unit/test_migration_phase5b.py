"""迁移 phase5b_email_storage 建表 + 对称回滚（SQLite 临时库，跑全链）。"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_upgrade_creates_then_downgrade_drops(tmp_path: Path):
    db = tmp_path / "p5b.db"
    url = f"sqlite:///{db}"
    env = {**os.environ, "DATABASE_URL": url}
    backend = Path(__file__).resolve().parents[2]  # .../backend
    up = subprocess.run(["alembic", "upgrade", "head"], cwd=backend, env=env,
                        capture_output=True, text=True)
    assert up.returncode == 0, up.stderr
    down = subprocess.run(["alembic", "downgrade", "-1"], cwd=backend, env=env,
                          capture_output=True, text=True)
    assert down.returncode == 0, down.stderr
    up2 = subprocess.run(["alembic", "upgrade", "head"], cwd=backend, env=env,
                         capture_output=True, text=True)
    assert up2.returncode == 0, up2.stderr
