# P0 解析准确率回归脚本（golden-master）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一个常驻、可复现的解析准确率回归工具——把主线当前对 36 份真实样本的解析输出（层级分布 + review 数 + 警告）快照成 golden 基线，并用一个 pytest 测试守住它，使后续动态字典移植 / 租户化 / 重构**任何静默改变解析输出**的改动都立即报错。

**Architecture:** 一个纯函数模块 `parser_accuracy.py`（递归 `ParseResult.chapters` 算层级分布、汇总一份语料的指标），一个生成 golden JSON 的步骤（运行一次、提交快照），一个对比测试（live 运行 vs golden、任何漂移即 fail）。golden 文件是"故意改动才更新"的契约：后续 plan 改变某文档分布时显式更新对应条目。

**Tech Stack:** Python 3.11+、SQLAlchemy 无关（纯解析层）、pytest、`app.parser.parse_docx`、stdlib `json`/`pathlib`/`collections.Counter`。

---

## File Structure

- `backend/app/parser/eval/__init__.py`（新）：空包标记。
- `backend/app/parser/eval/accuracy.py`（新）：`level_distribution()`、`evaluate_sample()`、`evaluate_corpus()`、`SAMPLE_ROOT` 常量、`__main__` CLI。**纯函数 + 读真实样本，不落库。**
- `backend/tests/regression/__init__.py`（新）：空包标记。
- `backend/tests/regression/test_parser_accuracy_baseline.py`（新）：golden-master 对比测试。
- `backend/tests/regression/parser_baseline.json`（新，由 Task 4 生成并提交）：golden 快照。
- `backend/tests/unit/parser/test_eval_accuracy.py`（新）：`level_distribution` / `evaluate_sample` 的合成单测（不依赖真实大样本，快、确定）。

> 放在 `app/parser/eval/` 而非一次性脚本，是为了让它**常驻、可被测试、可被后续 plan 复用**（避免重蹈 `eval_parser.py` 被删的覆辙）。

---

## Task 1: 层级分布纯函数 `level_distribution`

**Files:**
- Create: `backend/app/parser/eval/__init__.py`
- Create: `backend/app/parser/eval/accuracy.py`
- Test: `backend/tests/unit/parser/test_eval_accuracy.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/parser/test_eval_accuracy.py`：

```python
"""eval.accuracy 纯函数单测（P0）。"""
from __future__ import annotations

from app.parser.eval.accuracy import level_distribution
from app.parser.result import ParsedNode


def _node(level: int, *children: ParsedNode) -> ParsedNode:
    # ParsedNode 必填 level；其余字段用最小合法值，children 递归。
    return ParsedNode(level=level, children=list(children))


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
```

> 注意：`ParsedNode` 可能有其它必填字段。Step 3 实现前若构造报错，按 `result.py:ParsedNode` 的实际字段补默认值到 `_node` 助手（仅测试用）。

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && python -m pytest tests/unit/parser/test_eval_accuracy.py -v`
Expected: FAIL（`ModuleNotFoundError: app.parser.eval` 或 `ImportError: level_distribution`）

- [ ] **Step 3: 写最小实现**

`backend/app/parser/eval/__init__.py`：

```python
"""解析准确率评估工具（常驻、可测试）。"""
```

`backend/app/parser/eval/accuracy.py`：

```python
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
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && python -m pytest tests/unit/parser/test_eval_accuracy.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parser/eval/__init__.py backend/app/parser/eval/accuracy.py backend/tests/unit/parser/test_eval_accuracy.py
git commit -m "feat(eval): level_distribution 纯函数 + 单测 (P0 Task1)"
```

---

## Task 2: 单文档评估 `evaluate_sample`

**Files:**
- Modify: `backend/app/parser/eval/accuracy.py`
- Test: `backend/tests/unit/parser/test_eval_accuracy.py`

- [ ] **Step 1: 写失败测试**（追加到 `test_eval_accuracy.py`）

```python
from app.parser.eval.accuracy import evaluate_sample
from tests.unit.parser._docx_builder import styled_sop


def test_evaluate_sample_from_bytes() -> None:
    # 用合成 styled SOP 字节流，验证返回结构与字段（不依赖磁盘样本）
    metrics = evaluate_sample(styled_sop(), mode="standard")
    assert set(metrics) == {"distribution", "total_nodes", "review_required", "warning_stages"}
    assert metrics["distribution"]  # 非空
    assert metrics["total_nodes"] == sum(metrics["distribution"].values())
    assert isinstance(metrics["review_required"], int)
    assert isinstance(metrics["warning_stages"], dict)
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && python -m pytest tests/unit/parser/test_eval_accuracy.py::test_evaluate_sample_from_bytes -v`
Expected: FAIL（`ImportError: evaluate_sample`）

- [ ] **Step 3: 写最小实现**（追加到 `accuracy.py`）

```python
from collections import Counter as _Counter

from app.parser import parse_docx


def evaluate_sample(data: bytes, *, mode: str = "smart") -> dict:
    """解析单份 docx 字节流，返回可对账的指标字典。

    - distribution: {level: count}（层级分布，str 化在序列化层处理）
    - total_nodes:  章节树节点总数
    - review_required: 需人工复查的节点数
    - warning_stages: {stage: count} 各阶段警告计数（按 stage 聚合，稳定可比）
    """
    result = parse_docx(data, mode)
    dist = level_distribution(result.chapters)
    warn_stages: _Counter[str] = _Counter(w.stage for w in result.warnings)
    return {
        "distribution": dist,
        "total_nodes": sum(dist.values()),
        "review_required": result.review_required,
        "warning_stages": dict(sorted(warn_stages.items())),
    }
```

> 若 `Warning` 对象的属性名不是 `stage`/不存在，按 `result.py` 中警告类的实际字段调整（test_pipeline.py 已用 `w.stage`，应一致）。

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && python -m pytest tests/unit/parser/test_eval_accuracy.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parser/eval/accuracy.py backend/tests/unit/parser/test_eval_accuracy.py
git commit -m "feat(eval): evaluate_sample 单文档指标 + 单测 (P0 Task2)"
```

---

## Task 3: 语料遍历 `evaluate_corpus` + CLI

**Files:**
- Modify: `backend/app/parser/eval/accuracy.py`
- Test: `backend/tests/unit/parser/test_eval_accuracy.py`

- [ ] **Step 1: 写失败测试**（追加）

```python
from pathlib import Path

from app.parser.eval.accuracy import SAMPLE_ROOT, evaluate_corpus


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
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && python -m pytest tests/unit/parser/test_eval_accuracy.py -k corpus -v`
Expected: FAIL（`ImportError: evaluate_corpus` / `SAMPLE_ROOT`）

- [ ] **Step 3: 写最小实现**（追加到 `accuracy.py`，含 CLI）

```python
from pathlib import Path

# accuracy.py 在 backend/app/parser/eval/ → 上溯 4 层到仓库根，再进样本目录
_REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_ROOT = _REPO_ROOT / "docs" / "reference doc" / "typical word doc"


def evaluate_corpus(*, mode: str = "smart", root: Path | None = None) -> dict[str, dict]:
    """遍历样本根下全部 .docx，返回 {相对posix路径: 指标}。

    单文档解析异常不应中断整体评估：记为 {"error": "<repr>"}。
    """
    base = root or SAMPLE_ROOT
    out: dict[str, dict] = {}
    for path in sorted(base.rglob("*.docx")):
        rel = path.relative_to(base).as_posix()
        try:
            out[rel] = evaluate_sample(path.read_bytes(), mode=mode)
        except Exception as exc:  # noqa: BLE001 - 评估工具需健壮遍历
            out[rel] = {"error": repr(exc)}
    return out


def _main() -> None:  # pragma: no cover - CLI 手动核对入口
    import json
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "smart"
    print(json.dumps(evaluate_corpus(mode=mode), ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    _main()
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && python -m pytest tests/unit/parser/test_eval_accuracy.py -v`
Expected: PASS（5 passed）

手动核对（可选）：`cd backend && python -m app.parser.eval.accuracy smart | head -40` → 打印各文档指标 JSON。

- [ ] **Step 5: 提交**

```bash
git add backend/app/parser/eval/accuracy.py backend/tests/unit/parser/test_eval_accuracy.py
git commit -m "feat(eval): evaluate_corpus 遍历 36 份样本 + CLI (P0 Task3)"
```

---

## Task 4: 生成 golden 基线并提交

**Files:**
- Create: `backend/tests/regression/parser_baseline.json`（由命令生成）

- [ ] **Step 1: 生成两份模式的快照并合并为 golden 文件**

Run（在 `backend/` 下）：

```bash
cd backend && python -c "
import json
from app.parser.eval.accuracy import evaluate_corpus
golden = {'smart': evaluate_corpus(mode='smart'), 'standard': evaluate_corpus(mode='standard')}
import pathlib
p = pathlib.Path('tests/regression'); p.mkdir(parents=True, exist_ok=True)
(p / 'parser_baseline.json').write_text(json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
print('wrote', p / 'parser_baseline.json')
"
```

Expected: 打印 `wrote tests/regression/parser_baseline.json`

- [ ] **Step 2: 人工抽查 golden 是否合理**

Run: `cd backend && python -c "import json; g=json.load(open('tests/regression/parser_baseline.json', encoding='utf-8')); print('docs(smart)=', len(g['smart'])); print('TP=', g['smart'].get('TP试验程序.docx', {}).get('distribution'))"`
Expected: `docs(smart)= 36`（或实际样本数）；打印 TP 的当前主线分布（注意：主线**尚未移植 P1**，此处大概率是 `{1:32, 2:11}` 而非 `{1:29,2:11,3:3}`——这是预期的当前态，P1 plan 落地后会**显式更新**此条目）。

- [ ] **Step 3: 提交 golden**

```bash
git add backend/tests/regression/parser_baseline.json
git commit -m "test(regression): 主线解析输出 golden 基线快照 (P0 Task4)"
```

---

## Task 5: golden-master 回归测试

**Files:**
- Create: `backend/tests/regression/__init__.py`
- Create: `backend/tests/regression/test_parser_accuracy_baseline.py`

- [ ] **Step 1: 写测试（应直接通过——它守的是刚生成的 golden）**

`backend/tests/regression/__init__.py`：

```python
```

`backend/tests/regression/test_parser_accuracy_baseline.py`：

```python
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
```

- [ ] **Step 2: 运行验证通过**

Run: `cd backend && python -m pytest tests/regression/test_parser_accuracy_baseline.py -v`
Expected: PASS（2 passed —— live 与刚提交的 golden 完全一致）

- [ ] **Step 3: 验证它真的能抓漂移（临时反向验证，不提交）**

手动篡改 golden 一个数字后重跑，确认 FAIL，再 `git checkout` 还原：

```bash
cd backend && python - <<'PY'
import json, pathlib
p = pathlib.Path('tests/regression/parser_baseline.json')
g = json.loads(p.read_text(encoding='utf-8'))
first = sorted(g['smart'])[0]
g['smart'][first]['total_nodes'] = -999  # 人为漂移
p.write_text(json.dumps(g, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
PY
python -m pytest tests/regression/test_parser_accuracy_baseline.py -k smart -q  # 预期 FAIL
git checkout tests/regression/parser_baseline.json  # 还原
python -m pytest tests/regression/test_parser_accuracy_baseline.py -q  # 预期重新 PASS
```

Expected: 篡改后 FAIL（捕获漂移）→ 还原后 PASS。

- [ ] **Step 4: 提交**

```bash
git add backend/tests/regression/__init__.py backend/tests/regression/test_parser_accuracy_baseline.py
git commit -m "test(regression): golden-master 解析回归测试 (P0 Task5)"
```

---

## Task 6: 全量回归 + ruff

**Files:** 无（验证步骤）

- [ ] **Step 1: 跑解析器单测 + 新回归，确认零退化**

Run: `cd backend && python -m pytest tests/unit/parser tests/regression -v`
Expected: 全 PASS。

- [ ] **Step 2: ruff 检查新增文件**

Run: `cd backend && ruff check app/parser/eval tests/regression tests/unit/parser/test_eval_accuracy.py`
Expected: 无 error（按仓库既有风格修正 import 顺序等）。

- [ ] **Step 3: 提交（如有 lint 修正）**

```bash
git add -A && git commit -m "chore(eval): ruff 修正 (P0 Task6)" || echo "无需提交"
```

---

## Self-Review 记录

- **Spec 覆盖**：本 plan 实现 spec §3.2「第 0 步常驻准确率回归脚本」与 §3.1 基线的可执行化。其余 spec 章节由 P1–P5 覆盖。
- **占位符**：无 TBD/TODO；每个 code step 含完整代码与命令。两处「按实际字段调整」是**明确的兜底指引**（`ParsedNode` 额外必填字段、`Warning.stage` 属性名），非占位符——主体实现完整。
- **类型一致**：`level_distribution`/`evaluate_sample`/`evaluate_corpus`/`SAMPLE_ROOT` 在 Task 间签名一致；golden 结构 `{mode: {doc: metrics}}` 在 Task4 生成与 Task5 断言中一致。
- **当前态诚实**：Task4 Step2 明确指出主线 TP 尚无 P1、golden 会记录当前 `{1:32,2:11}`，P1 plan 落地时显式更新——不假装基线已是 `{1:29,2:11,3:3}`。
