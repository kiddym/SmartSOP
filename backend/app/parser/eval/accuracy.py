"""解析准确率评估：层级分布 + 单文档/语料指标 + CLI。

纯解析层，不落库、不做网络。供回归测试与人工核对复用，
取代历史上一次性、已删除的 eval_parser.py / eval_tree.py。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.parser import parse_docx
from app.parser.result import ParsedNode

# accuracy.py 在 backend/app/parser/eval/ → 上溯 4 层到仓库根，再进样本目录
_REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_ROOT = _REPO_ROOT / "docs" / "reference doc" / "typical word doc"


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


def evaluate_sample(data: bytes, *, mode: str = "smart") -> dict[str, Any]:
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


def evaluate_corpus(*, mode: str = "smart", root: Path | None = None) -> dict[str, dict[str, Any]]:
    """遍历样本根下全部 .docx，返回 {相对posix路径: 指标}。

    单文档解析异常不应中断整体评估：记为 {"error": "<repr>"}。
    """
    base = root or SAMPLE_ROOT
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(base.rglob("*.docx")):
        rel = path.relative_to(base).as_posix()
        try:
            out[rel] = evaluate_sample(path.read_bytes(), mode=mode)
        except Exception as exc:
            out[rel] = {"error": repr(exc)}
    return out


def _main() -> None:  # pragma: no cover - CLI 手动核对入口
    import json
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "smart"
    print(json.dumps(evaluate_corpus(mode=mode), ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    _main()
