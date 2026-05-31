"""eval.accuracy 纯函数单测（P0）。"""
from __future__ import annotations

from app.parser.eval.accuracy import (
    SAMPLE_ROOT,
    evaluate_corpus,
    evaluate_sample,
    level_distribution,
)
from app.parser.result import ParsedNode

from tests.unit.parser._docx_builder import styled_sop


def _node(level: int, *children: ParsedNode) -> ParsedNode:
    # ParsedNode 必填 id/title/level/content_type；其余字段用最小合法值，children 递归。
    return ParsedNode(
        id=f"n{level}",
        title=f"node-{level}",
        level=level,
        content_type="chapter",
        children=list(children),
    )


def test_level_distribution_counts_nested_tree() -> None:
    # 1 个 L1，下挂 2 个 L2，其中一个 L2 下挂 1 个 L3
    tree = [
        _node(1,
              _node(2, _node(3)),
              _node(2)),
    ]
    assert level_distribution(tree) == {1: 1, 2: 2, 3: 1}


def test_level_distribution_empty() -> None:
    assert level_distribution([]) == {}


def test_evaluate_sample_from_bytes() -> None:
    # 用合成 styled SOP 字节流，验证返回结构与字段（不依赖磁盘样本）
    metrics = evaluate_sample(styled_sop(), mode="standard")
    assert set(metrics) == {"distribution", "total_nodes", "review_required", "warning_stages"}
    assert metrics["distribution"]  # 非空
    assert metrics["total_nodes"] == sum(metrics["distribution"].values())
    assert isinstance(metrics["review_required"], int)
    assert isinstance(metrics["warning_stages"], dict)


def test_sample_root_exists_and_has_docx() -> None:
    assert SAMPLE_ROOT.is_dir(), f"样本根不存在: {SAMPLE_ROOT}"
    assert list(SAMPLE_ROOT.rglob("*.docx")), "样本根下无 .docx"


def test_evaluate_corpus_keys_are_relative_posix() -> None:
    corpus = evaluate_corpus(mode="smart")
    assert corpus, "语料结果为空"
    # 键是相对 SAMPLE_ROOT 的 posix 路径，稳定可跨平台比对
    for key, metrics in corpus.items():
        assert not key.startswith("/")
        assert "\\" not in key
        assert set(metrics) == {"distribution", "total_nodes", "review_required", "warning_stages"}
