"""eval.accuracy 纯函数单测（P0）。"""
from __future__ import annotations

from app.parser.eval.accuracy import level_distribution
from app.parser.result import ParsedNode


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
