"""三指标算法单测：normalize / LCS 对齐 / P-R / hierarchy / 3-gram coverage。"""
from __future__ import annotations

from scripts.eval.metrics import (
    content_cov_3gram,
    hierarchy_acc,
    lcs_align,
    normalize_body,
    normalize_title,
    title_prf,
)
from scripts.eval.models import GtChapter


def test_normalize_title_strips_whitespace_and_lowercases():
    assert normalize_title("  Heading 1  ") == "heading1"
    assert normalize_title("第 一 章　目的") == "第一章目的"  # 全角空格也归零
    assert normalize_title("HELLO World") == "helloworld"


def test_normalize_body_keeps_punctuation_and_normalizes_fullwidth():
    # NFKC 把全角 ！ 归一到半角 !；标点本身保留（不像 normalize_title 那样丢空格）
    assert normalize_body("Hello, world！") == "hello,world!"
    # 中文标点本身不在 NFKC 兼容映射里，会被保留
    assert normalize_body("第一章。") == "第一章。"


def test_lcs_align_order_sensitive():
    # GT 顺序: A B C；预测 A C B（顺序错位） → LCS 长度=2，不会全 3 对齐
    gt = ["a", "b", "c"]
    pred = ["a", "c", "b"]
    pairs = lcs_align(gt, pred)
    assert len(pairs) == 2
    # 必须保顺序（i 单调，j 单调）
    for (i1, j1), (i2, j2) in zip(pairs, pairs[1:], strict=False):
        assert i2 > i1 and j2 > j1


def test_lcs_align_empty():
    assert lcs_align([], []) == []
    assert lcs_align(["a"], []) == []
    assert lcs_align([], ["a"]) == []


def test_title_prf_basic():
    gt = [
        GtChapter(title="目的", level=1, source_idx=0),
        GtChapter(title="范围", level=1, source_idx=5),
        GtChapter(title="职责", level=1, source_idx=10),
    ]
    pred = [
        GtChapter(title="目的", level=1, source_idx=0),
        GtChapter(title="误判", level=1, source_idx=3),
        GtChapter(title="范围", level=1, source_idx=5),
    ]
    m = title_prf(gt, pred)
    assert m.tp == 2  # 目的、范围
    assert m.fn == 1  # 职责
    assert m.fp == 1  # 误判
    assert abs(m.precision - 2 / 3) < 1e-6
    assert abs(m.recall - 2 / 3) < 1e-6


def test_title_prf_empty_pred():
    gt = [GtChapter("a", 1, 0)]
    m = title_prf(gt, [])
    assert m.tp == 0 and m.fn == 1 and m.fp == 0
    assert m.precision == 0.0 and m.recall == 0.0 and m.f1 == 0.0


def test_title_prf_empty_gt_and_pred():
    # expected_empty 文档用：两端皆空 → 全 0，不报错
    m = title_prf([], [])
    assert m.tp == 0 and m.fn == 0 and m.fp == 0
    assert m.precision == 0.0 and m.recall == 0.0 and m.f1 == 0.0


def test_hierarchy_acc_aligned_levels():
    aligned = [
        (GtChapter("a", 1, 0), GtChapter("a", 1, 0)),
        (GtChapter("b", 2, 1), GtChapter("b", 2, 1)),
        (GtChapter("c", 1, 2), GtChapter("c", 2, 2)),  # level mismatch
    ]
    assert abs(hierarchy_acc(aligned) - 2 / 3) < 1e-6


def test_hierarchy_acc_no_alignments():
    assert hierarchy_acc([]) is None


def test_content_cov_3gram_full():
    gt = "abcdefghij" * 100
    pred = "abcdefghij" * 100
    assert content_cov_3gram(gt, pred) == 1.0


def test_content_cov_3gram_partial():
    gt = "abcdefgh"     # 3-grams: abc bcd cde def efg fgh = 6
    pred = "abcdef"     # 3-grams: abc bcd cde def = 4 (覆盖 gt 前 4)
    # gt 有 6 个 gram，pred 命中 4 个 → cov ≈ 4/6
    assert abs(content_cov_3gram(gt, pred) - 4 / 6) < 1e-6


def test_content_cov_3gram_empty_gt():
    # 防御：gt 空时返回 1.0（无要求 → 满分）
    assert content_cov_3gram("", "anything") == 1.0
