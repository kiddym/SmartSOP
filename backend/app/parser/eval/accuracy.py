"""解析准确率评估：层级分布 + 单文档/语料指标 + CLI。

纯解析层，不落库、不做网络。供回归测试与人工核对复用，
取代历史上一次性、已删除的 eval_parser.py / eval_tree.py。
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from app.parser.result import ParsedNode


def level_distribution(chapters: Iterable[ParsedNode]) -> dict[int, int]:
    """递归统计章节树各层级节点数，返回 {level: count}（按 level 升序）。"""
    counter: Counter[int] = Counter()

    def _walk(nodes: Iterable[ParsedNode]) -> None:
        for n in nodes:
            counter[n.level] += 1
            if n.children:
                _walk(n.children)

    _walk(chapters)
    return dict(sorted(counter.items()))
