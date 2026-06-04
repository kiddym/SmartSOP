"""env-gated MySQL 红线并发/硬化验证（SQLite 测不到的行为）。

SQLite 无行级锁、`FOR UPDATE [SKIP LOCKED]` 被静默忽略、连接天然串行——故批量解析
SKIP LOCKED 取件、序列 FOR UPDATE 取号、生成列 partial-unique 这些红线只能在 MySQL
上验证。本模块仅当设置 ``TEST_MYSQL_URL`` 时运行，缺省 skip。

覆盖：
1. SKIP LOCKED 取件不重不漏（batch_parse_service.claim_queued）。
2. 序列并发取号唯一、无跳号（sequence_service.next_value，FOR UPDATE 行锁）。
3. SOP 硬化迁移在 MySQL：17 表 company_id NOT NULL + 4 处 per-company 复合唯一 +
   tb_procedure/tb_folder 生成列及其 UNIQUE（partial-unique）保留。

用法：
    TEST_MYSQL_URL="mysql+pymysql://root@127.0.0.1:3306/sop_mysql_verify" \\
        .venv/bin/python -m pytest tests/test_mysql_concurrency.py -q
"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.services.batch_parse_service import claim_queued
from app.services.sequence_service import next_value
from app.tenant import bypass_tenant_scope

_ROOT = Path(__file__).resolve().parent.parent
_MYSQL_URL = os.environ.get("TEST_MYSQL_URL")

pytestmark = pytest.mark.skipif(
    not _MYSQL_URL,
    reason="设置 TEST_MYSQL_URL（指向可清空的 MySQL 库）以运行 MySQL 红线并发验证",
)

_NAIVE_NOW = datetime.now(UTC).replace(tzinfo=None) if _MYSQL_URL else None


@pytest.fixture(scope="module")
def engine() -> Engine:
    """全新 MySQL 库 upgrade head（幂等：已在 head 则 no-op），返回引擎。"""
    assert _MYSQL_URL is not None
    cfg = Config()
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    from app.config import settings

    settings.database_url = _MYSQL_URL  # env.py 读取此值
    command.upgrade(cfg, "head")
    eng = create_engine(_MYSQL_URL, pool_size=20, max_overflow=10)
    yield eng
    eng.dispose()


def _seed_company(conn, company_id: str) -> None:
    conn.execute(text("DELETE FROM tb_company WHERE id = :id"), {"id": company_id})
    conn.execute(
        text(
            "INSERT INTO tb_company"
            "(id,name,slug,status,locale,is_platform_admin_org,plan,subscription_status,"
            " created_at,updated_at) "
            "VALUES(:id,:id,:id,'active','zh',0,'free','active',NOW(6),NOW(6))"
        ),
        {"id": company_id},
    )


def test_skip_locked_claim_disjoint(engine: Engine) -> None:
    """两 Session 并发 claim：SKIP LOCKED 取件不重不漏，耗尽后为空。"""
    now = _NAIVE_NOW
    cid = "co_claim"
    with engine.begin() as c:
        c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        c.execute(text("DELETE FROM tb_batch_import_item WHERE company_id = :c"), {"c": cid})
        c.execute(text("DELETE FROM tb_batch_import_job WHERE company_id = :c"), {"c": cid})
        c.execute(
            text(
                "INSERT INTO tb_batch_import_job"
                "(id,company_id,folder_id,parse_mode,status,counts,created_at,updated_at,"
                " is_active) "
                "VALUES('jclaim',:c,'f1','standard','processing',JSON_OBJECT(),:n,:n,1)"
            ),
            {"c": cid, "n": now},
        )
        for i in range(4):
            c.execute(
                text(
                    "INSERT INTO tb_batch_import_item"
                    "(id,company_id,job_id,filename,content_hash,status,summary,"
                    " parse_blob_ref,docx_ref,review_revision,attempts,created_at,updated_at,"
                    " is_active) "
                    "VALUES(:id,:c,'jclaim',:fn,'','queued',JSON_OBJECT(),'','',1,0,:t,:n,1)"
                ),
                # created_at 互异：真实 item 逐条创建本就不同时刻；全同会让 InnoDB 对
                # `ORDER BY created_at LIMIT` 的等值簇取 gap 锁而锁住超出 LIMIT 的行。
                {
                    "id": f"clm{i}",
                    "c": cid,
                    "fn": f"f{i}.docx",
                    "t": now + timedelta(microseconds=i),
                    "n": now,
                },
            )
        c.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    # 核心红线 = "不重"：A 持锁未提交时，B 经 SKIP LOCKED 绝不取到 A 锁住的行。
    # （单次 claim 的锁范围依优化器选的索引可能超出 LIMIT，故"两次并发即取全"不是
    #  SKIP LOCKED 的保证；"不漏"是最终性——剩余行下一轮 poll 补取。）
    db_a, db_b = Session(engine), Session(engine)
    try:
        with bypass_tenant_scope():
            ids_a = {it.id for it in claim_queued(db_a, limit=2, now=now)}
            ids_b = {it.id for it in claim_queued(db_b, limit=2, now=now)}
        assert ids_a, "A 应取到 queued 项"
        assert ids_a.isdisjoint(ids_b), f"双 worker 取到同一 item（重复处理）A={ids_a} B={ids_b}"
        db_a.commit()
        db_b.commit()
    finally:
        db_a.close()
        db_b.close()

    # 排空：反复 claim 至空。每个 item 恰被 claim 一次（attempts==1）= 不重 + 不最终漏。
    db = Session(engine)
    try:
        with bypass_tenant_scope():
            while claim_queued(db, limit=4, now=now):
                db.commit()
        db.commit()
    finally:
        db.close()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT status, attempts FROM tb_batch_import_item "
                "WHERE company_id = :c ORDER BY id"
            ),
            {"c": cid},
        ).all()
    assert len(rows) == 4
    assert all(status == "parsing" for status, _ in rows), f"仍有未取件: {rows}"
    assert all(attempts == 1 for _, attempts in rows), f"存在重复 claim（attempts>1）: {rows}"


def test_sequence_concurrent_unique_no_gap(engine: Engine) -> None:
    """N 线程争用同 (company, scope)：FOR UPDATE 行锁使取号恰为 1..N，无重无跳。"""
    cid = "co_seq"
    n = 12
    with engine.begin() as c:
        _seed_company(c, cid)
        c.execute(text("DELETE FROM tb_sequence WHERE company_id = :c"), {"c": cid})
        c.execute(
            text(
                "INSERT INTO tb_sequence(id,company_id,scope,next_val,created_at,updated_at) "
                "VALUES(:id,:c,'wo',1,NOW(6),NOW(6))"
            ),
            {"id": str(uuid.uuid4()), "c": cid},
        )

    barrier = threading.Barrier(n)
    results: list[int] = []
    lock = threading.Lock()

    def worker(_: int) -> None:
        barrier.wait()  # 尽量同时开跑制造争用
        db = Session(engine)
        try:
            with bypass_tenant_scope():
                v = next_value(db, "wo", cid)
                db.commit()
            with lock:
                results.append(v)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=n) as ex:
        list(ex.map(worker, range(n)))

    assert sorted(results) == list(range(1, n + 1)), f"取号有重/跳: {sorted(results)}"


def test_sop_hardening_schema(engine: Engine) -> None:
    """SOP 硬化迁移在 MySQL 的 schema 效果：NOT NULL + 复合唯一 + 生成列 partial-unique。"""
    tenant_tables = [
        "tb_procedure_asset_reference",
        "tb_procedure_node",
        "tb_attachment",
        "tb_procedure_audit_log",
        "tb_folder_audit_log",
        "tb_heading_learning_event",
        "tb_batch_import_item",
        "tb_procedure_asset",
        "tb_procedure",
        "tb_folder_sequence",
        "tb_batch_import_job",
        "tb_folder",
        "tb_procedure_field",
        "tb_procedure_settings",
        "tb_procedure_source_docx",
        "tb_heading_style_rule",
        "tb_numbering_profile",
    ]
    with engine.connect() as conn:
        # ① 17 表 company_id NOT NULL
        nn = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE table_schema=DATABASE() AND column_name='company_id' "
                    "AND is_nullable='NO'"
                )
            )
        }
        missing = [t for t in tenant_tables if t not in nn]
        assert not missing, f"company_id 仍 nullable: {missing}"

        # ② 4 处 per-company SOP 复合唯一就位
        def composite(table: str) -> set[tuple[str, ...]]:
            rows = conn.execute(
                text(
                    "SELECT index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) "
                    "FROM information_schema.statistics "
                    "WHERE table_schema=DATABASE() AND table_name=:t AND non_unique=0 "
                    "GROUP BY index_name"
                ),
                {"t": table},
            )
            return {tuple(cols.split(",")) for _, cols in rows}

        assert ("company_id", "key") in composite("tb_procedure_field")
        assert ("company_id", "procedure_group_id") in composite("tb_procedure_source_docx")
        assert ("company_id", "sha256") in composite("tb_procedure_asset")
        assert ("company_id", "asset_id", "procedure_id") in composite(
            "tb_procedure_asset_reference"
        )

        # ③ tb_procedure/tb_folder 生成列（STORED）+ 其 UNIQUE 保留（partial-unique）
        gen = {
            (r[0], r[1])
            for r in conn.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema=DATABASE() AND extra LIKE '%STORED GENERATED%'"
                )
            )
        }
        for col in ("current_guard", "draft_guard", "active_code_version"):
            assert ("tb_procedure", col) in gen, f"tb_procedure.{col} 非生成列"
        assert ("tb_folder", "active_unique_key") in gen

        uniq_cols = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.statistics "
                    "WHERE table_schema=DATABASE() AND non_unique=0 "
                    "AND column_name IN "
                    "('current_guard','draft_guard','active_code_version','active_unique_key')"
                )
            )
        }
        assert uniq_cols == {
            "current_guard",
            "draft_guard",
            "active_code_version",
            "active_unique_key",
        }, f"生成列 UNIQUE 缺失: {uniq_cols}"
