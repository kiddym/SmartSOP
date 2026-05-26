"""GT 加载单测 — Tier1（自动从 styles.xml 派生）。

Tier2/3 在 test_gt_manual.py / test_gt_template.py 单独测。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.eval.gt import load_gt_style

REPO_ROOT = Path(__file__).resolve().parents[3]
STANDARD_DIR = REPO_ROOT / "docs" / "reference doc" / "typical word doc"


def test_load_gt_style_standard_template():
    """1_程序模板.docx 应识别出多个 styled heading（spec 验证表显示 12 个）。"""
    gt = load_gt_style(STANDARD_DIR / "1_程序模板.docx")
    assert gt.tier == "style"
    assert len(gt.chapters) >= 5  # 下限 5，允许后续调整
    # level 必须落在 1-3（4-6 已压到 3）
    assert all(1 <= c.level <= 3 for c in gt.chapters)
    # 顺序：source_idx 单调
    idxs = [c.source_idx for c in gt.chapters]
    assert idxs == sorted(idxs)
    # body_text 非空（不含标题，但有正文）
    assert len(gt.body_text) > 100


def test_load_gt_style_unstyled_doc_raises():
    """无格式文档应抛出明确 ValueError。"""
    unstyled = STANDARD_DIR / "无格式标题word" / "02记录控制程序.docx"
    with pytest.raises(ValueError, match="non-style"):
        load_gt_style(unstyled)
