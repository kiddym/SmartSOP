"""env-gated MySQL 批量解析/资产红线集成验证（bootstrap 修通后清"待手验"尾巴）。

这些行为的应用逻辑已由 SQLite 单测覆盖（test_batch_parse_service / test_batch_review_service
/ test_asset_*），但**从未在 MySQL 上跑过**——因整链迁移曾卡 1101 无法 bootstrap（见
[[mysql-text-default-blocks-bootstrap]]）。bootstrap 修通后，本模块在 MySQL 实跑确认无
MySQL 特异性意外（DATETIME(6) 租约比较、JSON 列、per-company 唯一约束 DB 层强制、生成列
随 is_active 重算）。仅当设置 ``TEST_MYSQL_URL`` 时运行，缺省 skip。

覆盖（[[batch-word-parsing-mvp]] 的"集成验证清单"）：
1. 崩溃自愈 reaper：过期租约 parsing→queued / applying→review，未过期不动。
2. 跨租户领取不泄漏：bypass 跨租户取件且每项保留自身 company_id；租户上下文内只见本租户。
3. 图片提升资产 per-company sha256 去重 + 跨公司不泄漏 + 共享物理文件。
4. undo：软删已落库 Procedure 使 MySQL STORED 生成列 guard 重算为 NULL（释放 partial-unique）。

> FOR UPDATE 行锁序列化原语另由 test_mysql_concurrency 的并发取号(no-dup) 证明；资产
> find_or_create 与 GC delete_asset_locked 复用同一 with_for_update 原语。

用法：
    TEST_MYSQL_URL="mysql+pymysql://root@127.0.0.1:3306/sop_mysql_verify" \\
        .venv/bin/python -m pytest tests/test_mysql_integration.py -q
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app import tenant
from app.config import settings
from app.models.batch import BatchImportItem
from app.services import asset_service, batch_parse_service, batch_review_service

_ROOT = Path(__file__).resolve().parent.parent
_MYSQL_URL = os.environ.get("TEST_MYSQL_URL")

pytestmark = pytest.mark.skipif(
    not _MYSQL_URL,
    reason="设置 TEST_MYSQL_URL（指向可清空的 MySQL 库）以运行 MySQL 集成验证",
)

_NOW = datetime.now(UTC).replace(tzinfo=None) if _MYSQL_URL else None


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    """全新 MySQL 库 upgrade head（幂等）+ storage_dir 指向临时目录，返回引擎。"""
    assert _MYSQL_URL is not None
    cfg = Config()
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    settings.database_url = _MYSQL_URL  # env.py 读取此值
    command.upgrade(cfg, "head")
    with tempfile.TemporaryDirectory() as tmp:
        old_storage = settings.storage_dir
        settings.storage_dir = tmp
        eng = create_engine(_MYSQL_URL, pool_size=20, max_overflow=10)
        try:
            yield eng
        finally:
            eng.dispose()
            settings.storage_dir = old_storage


def _seed_company(conn, cid: str) -> None:
    conn.execute(text("DELETE FROM tb_company WHERE id = :id"), {"id": cid})
    conn.execute(
        text(
            "INSERT INTO tb_company"
            "(id,name,slug,status,locale,is_platform_admin_org,plan,subscription_status,"
            " created_at,updated_at) "
            "VALUES(:id,:id,:id,'active','zh',0,'free','active',NOW(6),NOW(6))"
        ),
        {"id": cid},
    )


def _seed_job(conn, *, cid: str, job_id: str) -> None:
    conn.execute(
        text(
            "INSERT INTO tb_batch_import_job"
            "(id,company_id,folder_id,parse_mode,status,counts,created_at,updated_at,is_active) "
            "VALUES(:j,:c,'f1','standard','processing',JSON_OBJECT(),:n,:n,1)"
        ),
        {"j": job_id, "c": cid, "n": _NOW},
    )


def _seed_item(
    conn, *, item_id: str, cid: str, job_id: str, status: str, leased_until, created_offset: int = 0
) -> None:
    conn.execute(
        text(
            "INSERT INTO tb_batch_import_item"
            "(id,company_id,job_id,filename,content_hash,status,summary,parse_blob_ref,"
            " docx_ref,review_revision,attempts,leased_until,created_at,updated_at,is_active) "
            "VALUES(:id,:c,:j,:fn,'',:st,JSON_OBJECT(),'','',1,0,:lu,:ct,:n,1)"
        ),
        {
            "id": item_id,
            "c": cid,
            "j": job_id,
            "fn": f"{item_id}.docx",
            "st": status,
            "lu": leased_until,
            "ct": _NOW + timedelta(microseconds=created_offset),
            "n": _NOW,
        },
    )


def test_reaper_reclaims_expired_leases(engine: Engine) -> None:
    """reclaim_expired：过期租约 parsing→queued / applying→review，未过期不动。"""
    now = _NOW
    cid = "co_reaper"
    expired = now - timedelta(seconds=60)
    fresh = now + timedelta(seconds=600)
    with engine.begin() as c:
        c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        c.execute(text("DELETE FROM tb_batch_import_item WHERE company_id = :c"), {"c": cid})
        c.execute(text("DELETE FROM tb_batch_import_job WHERE company_id = :c"), {"c": cid})
        _seed_job(c, cid=cid, job_id="jr")
        _seed_item(c, item_id="p_exp", cid=cid, job_id="jr", status="parsing", leased_until=expired)
        _seed_item(c, item_id="p_fresh", cid=cid, job_id="jr", status="parsing", leased_until=fresh)
        _seed_item(
            c, item_id="a_exp", cid=cid, job_id="jr", status="applying", leased_until=expired
        )
        _seed_item(
            c, item_id="a_fresh", cid=cid, job_id="jr", status="applying", leased_until=fresh
        )
        c.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    db = Session(engine)
    try:
        n = batch_parse_service.reclaim_expired(db, now=now)
        db.commit()
    finally:
        db.close()
    assert n == 2, f"应回收 2 个过期项，实回收 {n}"

    with engine.connect() as conn:
        rows = dict(
            conn.execute(
                text(
                    "SELECT id, CONCAT(status, IF(leased_until IS NULL,'/none','/kept')) "
                    "FROM tb_batch_import_item WHERE company_id = :c"
                ),
                {"c": cid},
            ).all()
        )
    assert rows["p_exp"] == "queued/none", rows
    assert rows["a_exp"] == "review/none", rows
    assert rows["p_fresh"] == "parsing/kept", rows
    assert rows["a_fresh"] == "applying/kept", rows


def test_cross_tenant_claim_no_leak(engine: Engine) -> None:
    """bypass 跨租户取件且每项保留自身 company_id；租户上下文内只见本租户。"""
    now = _NOW
    a, b = "co_xa", "co_xb"
    with engine.begin() as c:
        c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        # bypass claim 是全局取件 → 须从干净 batch 表起，否则会捞到其它测试的残留 queued 项
        c.execute(text("DELETE FROM tb_batch_import_item"))
        c.execute(text("DELETE FROM tb_batch_import_job"))
        for cid in (a, b):
            _seed_job(c, cid=cid, job_id=f"j_{cid}")
            for i in range(2):
                _seed_item(
                    c,
                    item_id=f"{cid}_{i}",
                    cid=cid,
                    job_id=f"j_{cid}",
                    status="queued",
                    leased_until=None,
                    created_offset=i,
                )
        c.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    # 租户上下文内（无 bypass）：只见本租户的 2 项
    db = Session(engine)
    try:
        token = tenant.set_current_company_id(a)
        try:
            scoped = batch_parse_service.claim_queued(db, limit=10, now=now)
            scoped_cids = {it.company_id for it in scoped}
        finally:
            tenant.reset_current_company_id(token)
        db.rollback()  # 不保留这次领取
        assert scoped_cids == {a}, f"租户上下文领取泄漏到他租户: {scoped_cids}"
        assert len(scoped) == 2
    finally:
        db.close()

    # bypass：跨租户取全 4 项，每项保留自身 company_id（worker 据此 per-item 切上下文）
    db = Session(engine)
    try:
        with tenant.bypass_tenant_scope():
            claimed = batch_parse_service.claim_queued(db, limit=10, now=now)
            by_company: dict[str, int] = {}
            for it in claimed:
                # seed 时 id 形如 "<cid>_<i>"，company_id 须与 id 前缀一致（无错配/泄漏）
                assert it.id.startswith(it.company_id), f"item {it.id} 错配 company {it.company_id}"
                by_company[it.company_id] = by_company.get(it.company_id, 0) + 1
        db.commit()
    finally:
        db.close()
    assert by_company == {a: 2, b: 2}, f"跨租户取件分布异常: {by_company}"


def test_asset_per_company_dedup_and_no_cross_leak(engine: Engine) -> None:
    """图片提升：同字节 per-company sha256 去重；跨公司各一行但共享物理文件。"""
    a, b = "co_aa", "co_ab"
    with engine.begin() as c:
        c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for cid in (a, b):
            c.execute(text("DELETE FROM tb_procedure_asset WHERE company_id = :c"), {"c": cid})
        c.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        # 资产经 app Session 落库（FK 检查开）→ 须有真实 company 行
        _seed_company(c, a)
        _seed_company(c, b)
    data = b"shared-image-bytes-\x89PNG-fake"

    db = Session(engine)
    try:
        # 公司 A：建一次，再 find 一次 → 同一行（per-company 去重）
        token = tenant.set_current_company_id(a)
        try:
            a1 = asset_service.find_or_create_asset(db, data, ext=".png")
            db.commit()
            a2 = asset_service.find_or_create_asset(db, data, ext=".png")
            db.commit()
        finally:
            tenant.reset_current_company_id(token)
        assert a1.id == a2.id, "同公司同字节未去重"
        assert a1.company_id == a, "资产未落入当前租户"

        # 公司 B：同字节 → 不同行（跨公司不泄漏），但 storage_path 相同（共享物理文件）
        token = tenant.set_current_company_id(b)
        try:
            b1 = asset_service.find_or_create_asset(db, data, ext=".png")
            db.commit()
        finally:
            tenant.reset_current_company_id(token)
        assert b1.id != a1.id, "跨公司资产被错误复用（租户泄漏）"
        assert b1.company_id == b
        assert b1.sha256 == a1.sha256
        assert b1.storage_path == a1.storage_path, "同字节应共享 sha256 分桶物理文件"
    finally:
        db.close()


def test_undo_recomputes_generated_guard_columns(engine: Engine) -> None:
    """undo 软删 Procedure → MySQL STORED 生成列 current_guard/active_code_version 重算为 NULL。"""
    cid = "co_undo"
    pid, gid, jid, iid = "p_undo", "g_undo", "j_undo", "i_undo"
    with engine.begin() as c:
        c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        c.execute(text("DELETE FROM tb_procedure WHERE company_id = :c"), {"c": cid})
        c.execute(text("DELETE FROM tb_batch_import_item WHERE company_id = :c"), {"c": cid})
        c.execute(text("DELETE FROM tb_batch_import_job WHERE company_id = :c"), {"c": cid})
        # 当前+激活版本：生成列 current_guard / active_code_version 应非 NULL
        c.execute(
            text(
                "INSERT INTO tb_procedure"
                "(id,company_id,procedure_group_id,is_current,folder_id,code,name,version,"
                " version_change_log,status,is_read,custom_values,risk_level,quality_level,"
                " level_of_use,revision,created_at,updated_at,is_active,signoff_enabled) "
                "VALUES(:id,:c,:g,1,'f1','C-001','P',1,JSON_ARRAY(),'RELEASED',0,JSON_OBJECT(),"
                " 1,1,'reference',1,:n,:n,1,0)"
            ),
            {"id": pid, "c": cid, "g": gid, "n": _NOW},
        )
        _seed_job(c, cid=cid, job_id=jid)
        c.execute(
            text(
                "INSERT INTO tb_batch_import_item"
                "(id,company_id,job_id,filename,content_hash,status,summary,parse_blob_ref,"
                " docx_ref,review_revision,attempts,created_procedure_id,created_at,updated_at,"
                " is_active) "
                "VALUES(:id,:c,:j,'u.docx','','applied',JSON_OBJECT(),'','',1,0,:pid,:n,:n,1)"
            ),
            {"id": iid, "c": cid, "j": jid, "pid": pid, "n": _NOW},
        )
        c.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    def guards() -> tuple:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT current_guard, active_code_version FROM tb_procedure WHERE id = :p"),
                {"p": pid},
            ).one()

    cg, acv = guards()
    assert cg == gid and acv == "C-001::1", f"当前激活版本生成列应非 NULL: {cg}, {acv}"

    db = Session(engine)
    try:
        token = tenant.set_current_company_id(cid)
        try:
            batch_review_service.undo_item(db, jid, iid)
            db.commit()
        finally:
            tenant.reset_current_company_id(token)
        item = db.get(BatchImportItem, iid)
        assert item is not None and item.status == "review"
        assert item.created_procedure_id is None
    finally:
        db.close()

    cg2, acv2 = guards()
    assert cg2 is None and acv2 is None, f"软删后生成列应重算为 NULL: {cg2}, {acv2}"
