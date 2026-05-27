"""Tier 2 manual GT 加载器单测：6 份固化 fixture 都能加载且字段健全。"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.eval.gt import load_gt_manual

REPO_ROOT = Path(__file__).resolve().parents[3]
MANUAL_DOCS = [
    "docs/reference doc/typical word doc/无格式标题word/3.危险源监控措施.docx",
    "docs/reference doc/typical word doc/无格式标题word/02记录控制程序.docx",
    "docs/reference doc/typical word doc/无格式标题word/05人力资源控制程序.docx",
    "docs/reference doc/typical word doc/无格式标题word/CW-WI-7.4-01外发作业指导书及质量控制程序.docx",
    "docs/reference doc/typical word doc/无格式标题word/有限空间作业管理办法.docx",
    "docs/reference doc/typical word doc/extra doc/01-公司环境分析控制程序.docx",
]

# 预期 chapter 数（与 manual_gt_review.md ack 后一致）
EXPECTED_COUNTS = {
    "3.危险源监控措施.docx": 5,
    "02记录控制程序.docx": 21,
    "05人力资源控制程序.docx": 22,
    # CW-WI 补全 5.1-5.8 + 6.2-6.11 (eval r3)：原 v3 GT 跳过了平行 sub-headings
    "CW-WI-7.4-01外发作业指导书及质量控制程序.docx": 28,
    "有限空间作业管理办法.docx": 6,
    # 01-公司环境补全 3.2-3.4 + 5.2-5.4（同 r3）
    "01-公司环境分析控制程序.docx": 16,
}


@pytest.mark.parametrize("rel", MANUAL_DOCS)
def test_load_gt_manual_loads(rel):
    docx = REPO_ROOT / rel
    gt = load_gt_manual(docx)
    assert gt.tier == "manual"
    assert gt.reviewed is True
    assert len(gt.chapters) == EXPECTED_COUNTS[docx.name]
    assert all(1 <= c.level <= 3 for c in gt.chapters)
    # source_idx 单调（按 docx 顺序）
    idxs = [c.source_idx for c in gt.chapters]
    assert idxs == sorted(idxs)
    # body_text 不为空
    assert len(gt.body_text) > 50


def test_load_gt_manual_missing_fixture_raises(tmp_path):
    """无 fixture 的 docx 应抛 FileNotFoundError（非 manual GT 范围）。"""
    fake = tmp_path / "未知文档.docx"
    fake.write_bytes(b"PK\x03\x04dummy")  # 不会被打开因为 fixture 已先 check
    with pytest.raises(FileNotFoundError, match="manual GT not found"):
        load_gt_manual(fake)
