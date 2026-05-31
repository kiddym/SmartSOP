"""解析准确率评估：层级分布 + 单文档/语料指标 + CLI。

纯解析层，不落库、不做网络。供回归测试与人工核对复用，
取代历史上一次性、已删除的 eval_parser.py / eval_tree.py。
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from app.parser import parse_docx
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


def evaluate_sample(data: bytes, *, mode: str = "smart") -> dict:
    """解析单份 docx 字节流，返回可对账的指标字典。

    - distribution: {level: count}（层级分布，str 化在序列化层处理）
    - total_nodes:  章节树节点总数
    - review_required: 需人工复查的节点数
    - warning_stages: {stage: count} 各阶段警告计数（按 stage 聚合，稳定可比）
    """
    result = parse_docx(data, mode)
    dist = level_distribution(result.chapters)
    warn_stages: Counter[str] = Counter(w.stage for w in result.warnings)
    return {
        "distribution": dist,
        "total_nodes": sum(dist.values()),
        "review_required": result.review_required,
        "warning_stages": dict(sorted(warn_stages.items())),
    }
