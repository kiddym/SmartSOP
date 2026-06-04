"""资产 GC 跨租户：sha256 改 per-company 复合唯一后，两公司同字节各一行但共享同一
物理文件（storage_path 按 sha256 全局分桶）。GC 删除一方时不得删掉仍被另一方引用的
共享文件，否则另一公司的 active 资产被孤立（图裂/读失败）。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app import tenant
from app.models.base import utcnow
from app.models.company import Company
from app.services import asset_service
from tests.unit.parser._docx_builder import tiny_png


def _company(db: Session, name: str, slug: str) -> str:
    c = Company(name=name, slug=slug)
    db.add(c)
    db.flush()
    return c.id


def test_gc_keeps_file_shared_by_other_tenant(db: Session, storage_tmp: Path) -> None:
    png = tiny_png()
    a_id = _company(db, "A公司", "a-co")
    b_id = _company(db, "B公司", "b-co")

    tok = tenant.set_current_company_id(a_id)
    try:
        asset_a = asset_service.find_or_create_asset(db, png, ext=".png")
    finally:
        tenant.reset_current_company_id(tok)
    tok = tenant.set_current_company_id(b_id)
    try:
        asset_b = asset_service.find_or_create_asset(db, png, ext=".png")
    finally:
        tenant.reset_current_company_id(tok)
    db.flush()

    # 两公司各自一行，但共享同一物理文件
    assert asset_a.id != asset_b.id
    assert asset_a.company_id == a_id and asset_b.company_id == b_id
    assert asset_a.storage_path == asset_b.storage_path
    shared = storage_tmp / asset_a.storage_path
    assert shared.exists()

    # 让 A 的 asset 过 grace 并 GC（ref_count=0）
    asset_a.updated_at = utcnow() - timedelta(hours=48)
    db.flush()
    tok = tenant.set_current_company_id(a_id)
    try:
        deleted = asset_service.delete_asset_locked(db, asset_a.id, grace_hours=24, now=utcnow())
    finally:
        tenant.reset_current_company_id(tok)
    assert deleted is True

    # B 仍引用同一文件 → 共享物理文件不得被删
    assert shared.exists(), "共享物理文件被误删，B 公司资产被孤立"
