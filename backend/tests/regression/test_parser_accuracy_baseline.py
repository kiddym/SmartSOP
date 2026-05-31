"""解析准确率 golden-master 回归（P0）。

live 运行 vs 提交的 golden 快照；任何漂移即 fail。
**故意改动解析输出的 plan 必须显式重生成 golden（见 P0 Task4 命令）并在该 commit 解释原因。**
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.parser.eval.accuracy import evaluate_corpus

_GOLDEN = Path(__file__).parent / "parser_baseline.json"


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(_GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("mode", ["smart", "standard"])
def test_corpus_matches_golden(golden: dict, mode: str) -> None:
    live = evaluate_corpus(mode=mode)
    expected = golden[mode]
    # 文档集合一致
    assert set(live) == set(expected), (
        f"[{mode}] 样本集合漂移：仅 live={set(live) - set(expected)}，"
        f"仅 golden={set(expected) - set(live)}"
    )
    # 逐文档指标一致（json round-trip 后 level 键为 str，统一比对序列化形态）
    live_json = json.loads(json.dumps(live, ensure_ascii=False, sort_keys=True))
    for doc in sorted(expected):
        assert live_json[doc] == expected[doc], (
            f"[{mode}] {doc} 解析输出漂移：\n live={live_json[doc]}\n golden={expected[doc]}\n"
            "若为有意改动，重生成 golden（P0 Task4）并在 commit 说明。"
        )
