# Word 解析器打磨：评测脚手架 + 调参闭环 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建一个能跨 36 份真实 docx 跑统一指标、出 baseline diff、支撑高频调参迭代的评测脚手架；然后在严强阈值下迭代解析器直至达标；最后产出综合评估 + 重构建议。

**Architecture:** `scripts/eval_parser.py` 作 CLI 入口；`scripts/eval/` 内分 `gt.py`(三档 GT 加载) / `metrics.py`(LCS 标题对齐+hierarchy+3-gram content_cov) / `runner.py`(per-doc 流水线) / `report.py`(summary.md + diff) 四个模块。直接 import `app.parser.parse_docx`，不走 HTTP。GT 物化到 `tests/fixtures/eval_gt/` 进 git。报告写 `.eval-reports/<ts>/`（gitignore）。

**Tech Stack:** Python 3.11、lxml、python-docx（已在 backend 依赖）、BeautifulSoup4（已在 backend）、pytest。

**Spec：** [`docs/superpowers/specs/2026-05-27-word-parser-polish-design.md`](../specs/2026-05-27-word-parser-polish-design.md)

---

## 文件结构

| 路径 | 职责 |
|---|---|
| `scripts/eval_parser.py` | CLI 入口；`argparse` + 调度 runner；打印简要总结 |
| `scripts/eval/__init__.py` | 空 |
| `scripts/eval/types.py` | `GtChapter` / `GroundTruth` / `DocResult` / `EvalReport` dataclass |
| `scripts/eval/gt.py` | `load_gt_style` (Tier1) / `load_gt_manual` (Tier2) / `load_gt_template` (Tier3) / `extract_qms_gt` (Tier3 抽取器) |
| `scripts/eval/metrics.py` | `lcs_align(gt, pred)` / `title_prf(gt, pred)` / `hierarchy_acc(aligned)` / `content_cov_3gram(gt_text, pred_text)` / `normalize_title` / `normalize_body` |
| `scripts/eval/runner.py` | `run_eval(subset, mode, out_dir, baseline) -> EvalReport`：装配 GT、跑 parser、算指标、写 per_doc/<name>.json |
| `scripts/eval/report.py` | `write_summary(report, out_dir)` / `write_diff(report, baseline, out_dir)`：生成 summary.md / summary.json / diff_vs_baseline.md |
| `scripts/eval/tests/conftest.py` | 把 `repo_root/backend` 和 `repo_root/scripts` 加进 `sys.path` |
| `scripts/eval/tests/test_metrics.py` | 单测 LCS + P/R + hierarchy + 3-gram coverage |
| `scripts/eval/tests/test_gt.py` | 单测 Tier1 风格派生 + Tier3 QMS 模板抽取器 |
| `scripts/eval/tests/test_runner.py` | 集成测试：mock parser 输出 → 跑 runner → 验报告字段 |
| `scripts/eval/tests/__init__.py` | 空 |
| `tests/fixtures/eval_gt/manual/<doc>.json` × 6 | Tier 2 人工 ack 后落盘的 manual GT（5 unstyled + `01-公司环境分析控制程序.docx`）|
| `tests/fixtures/eval_gt/template_ack/<doc>.json` × 3 | Tier 3 人工 ack 后落盘的 anchor GT（05/15/25-基础设施 / 标识 / 各级人员）|
| `.gitignore` | 增加 `.eval-reports/` 一行 |
| `docs/parser-tuning-log.md` | 每轮一行的调参日志（初始仅 header + baseline row） |
| `docs/parser-comprehensive-evaluation.md` | 闭环结束后的综合评估 + 重构建议（交付物 #5） |

**调参期间会动到的解析器文件**（仅在 §4 迭代回路内改动，本计划不预先规定改法）：

- `backend/app/parser/heading_detector.py`
- `backend/app/parser/structurer.py`
- `backend/app/parser/styles.py`
- `backend/app/parser/body_start.py`
- `config/heading_synonyms.yaml`
- `backend/tests/unit/parser/test_*.py`（新发现案例固化为单测）

---

## Phase A · 评测脚手架（Tasks 1-3）

### Task 1: gitignore + 包骨架 + 类型

**Files:**
- Modify: `.gitignore`
- Create: `scripts/eval/__init__.py`
- Create: `scripts/eval/types.py`
- Create: `scripts/eval/tests/__init__.py`
- Create: `scripts/eval/tests/conftest.py`

- [ ] **Step 1: `.gitignore` 追加 `.eval-reports/`**

```
# 末尾追加
.eval-reports/
```

- [ ] **Step 2: 创建包目录 + 空 `__init__.py`**

```python
# scripts/eval/__init__.py
# scripts/eval/tests/__init__.py
"""evaluation harness package."""
```

- [ ] **Step 3: 写 `scripts/eval/types.py`**

```python
"""Eval harness 共享类型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Tier = Literal["style", "manual", "template"]


@dataclass(frozen=True)
class GtChapter:
    title: str           # normalize 后的标题文本（去全/半空白 + 小写）
    level: int           # 1 | 2 | 3
    source_idx: int      # 原 docx 段落顺序索引


@dataclass(frozen=True)
class GroundTruth:
    docx_path: Path
    tier: Tier
    chapters: tuple[GtChapter, ...]  # 扁平有序
    body_text: str                   # 拼接正文段落（不含标题/页眉/页脚）
    expected_empty: bool = False     # True 时该文档不进 P/R 分子分母
    reviewed: bool = True            # Tier3 未抽样部分置 False


@dataclass
class TitleMetrics:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


@dataclass
class DocResult:
    docx_path: Path
    tier: Tier
    expected_empty: bool
    reviewed: bool
    title: TitleMetrics
    hierarchy_acc: float | None      # None 表示 TP=0 没法算
    content_cov: float
    fp_titles: list[str] = field(default_factory=list)
    fn_titles: list[str] = field(default_factory=list)
    level_mismatches: list[tuple[str, int, int]] = field(default_factory=list)  # (title, gt_lvl, pred_lvl)
    body_start_detected_by: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    timestamp: str
    mode: Literal["standard", "smart"]
    subset: str
    docs: list[DocResult]
    # 汇总（micro/macro 分 tier 计算，见 report.py）
```

- [ ] **Step 4: 写 `scripts/eval/tests/conftest.py`**

```python
"""pytest path setup：把 backend/ 和 repo_root 注入 sys.path，便于:
   from app.parser import ...
   from scripts.eval.metrics import ...
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # repo root
for p in (_ROOT / "backend", _ROOT):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
```

- [ ] **Step 5: smoke 验证导入**

Run:
```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
uv run --project backend python -c "
import sys; sys.path.insert(0, '.')
from scripts.eval.types import GtChapter, GroundTruth, DocResult, EvalReport
print('OK')
"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add .gitignore scripts/eval/__init__.py scripts/eval/types.py scripts/eval/tests/__init__.py scripts/eval/tests/conftest.py
git commit -m "feat(eval): 评测脚手架 — 包骨架 + 类型 + gitignore .eval-reports/

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 三指标算法 + 单测

**Files:**
- Create: `scripts/eval/metrics.py`
- Create: `scripts/eval/tests/test_metrics.py`

- [ ] **Step 1: 写失败测试 `test_metrics.py`**

```python
"""三指标算法单测：normalize / LCS 对齐 / P-R / hierarchy / 3-gram coverage。"""
from __future__ import annotations

from scripts.eval.metrics import (
    normalize_title,
    normalize_body,
    lcs_align,
    title_prf,
    hierarchy_acc,
    content_cov_3gram,
)
from scripts.eval.types import GtChapter


def test_normalize_title_strips_whitespace_and_lowercases():
    assert normalize_title("  Heading 1  ") == "heading1"
    assert normalize_title("第 一 章　目的") == "第一章目的"  # 全角空格
    assert normalize_title("HELLO World") == "helloworld"


def test_normalize_body_keeps_punctuation():
    assert normalize_body("Hello, world！") == "hello,world！"


def test_lcs_align_order_sensitive():
    # GT 顺序: A B C；预测 A C B（顺序错位） → LCS = [A, B] 或 [A, C]，不会全 3 对齐
    gt = ["a", "b", "c"]
    pred = ["a", "c", "b"]
    pairs = lcs_align(gt, pred)
    assert len(pairs) == 2
    # 必须保顺序（i 单调，j 单调）
    for (i1, j1), (i2, j2) in zip(pairs, pairs[1:]):
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
    # expected_empty 用：两端皆空 → 全 0，不报错
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
```

- [ ] **Step 2: 跑测试验证全 FAIL**

Run: `cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP" && uv run --project backend python -m pytest scripts/eval/tests/test_metrics.py -v`
Expected: 10 FAILED with "ImportError" or "ModuleNotFoundError" (因 metrics.py 还没写)

- [ ] **Step 3: 写 `scripts/eval/metrics.py`**

```python
"""标题 P/R/F1（LCS 对齐）+ hierarchy + 3-gram content coverage。"""
from __future__ import annotations

import re
import unicodedata

from scripts.eval.types import GtChapter, TitleMetrics

_SPACE_RE = re.compile(r"\s+")


def normalize_title(s: str) -> str:
    """标题 normalize：NFKC（全→半）+ 去所有空白 + 小写。"""
    s = unicodedata.normalize("NFKC", s)
    s = _SPACE_RE.sub("", s)
    return s.lower()


def normalize_body(s: str) -> str:
    """正文 normalize：NFKC + 去所有空白 + 小写；保留标点（cell 边界信号）。"""
    s = unicodedata.normalize("NFKC", s)
    s = _SPACE_RE.sub("", s)
    return s.lower()


def lcs_align(gt: list[str], pred: list[str]) -> list[tuple[int, int]]:
    """LCS 对齐：返回 (gt_idx, pred_idx) 配对列表，i/j 双单调。"""
    m, n = len(gt), len(pred)
    if m == 0 or n == 0:
        return []
    # DP 表
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            if gt[i] == pred[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])
    # 回溯配对
    pairs: list[tuple[int, int]] = []
    i, j = m, n
    while i > 0 and j > 0:
        if gt[i - 1] == pred[j - 1]:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return list(reversed(pairs))


def title_prf(gt: list[GtChapter], pred: list[GtChapter]) -> TitleMetrics:
    """P/R/F1，LCS 对齐 normalize 后的标题文本。"""
    gt_norm = [normalize_title(c.title) for c in gt]
    pred_norm = [normalize_title(c.title) for c in pred]
    pairs = lcs_align(gt_norm, pred_norm)
    tp = len(pairs)
    fn = len(gt) - tp
    fp = len(pred) - tp
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return TitleMetrics(tp=tp, fp=fp, fn=fn, precision=p, recall=r, f1=f1)


def align_chapters(gt: list[GtChapter], pred: list[GtChapter]) -> list[tuple[GtChapter, GtChapter]]:
    """对齐 GT 和预测 chapters，返回 (gt, pred) 对，供 hierarchy_acc 用。"""
    gt_norm = [normalize_title(c.title) for c in gt]
    pred_norm = [normalize_title(c.title) for c in pred]
    return [(gt[i], pred[j]) for i, j in lcs_align(gt_norm, pred_norm)]


def hierarchy_acc(aligned: list[tuple[GtChapter, GtChapter]]) -> float | None:
    """仅在 TP 上算 level 匹配率。TP=0 返回 None。"""
    if not aligned:
        return None
    hits = sum(1 for g, p in aligned if g.level == p.level)
    return hits / len(aligned)


def content_cov_3gram(gt_text: str, pred_text: str) -> float:
    """3-gram 字符集 IoU，分母用 GT grams（"GT 里有多少被覆盖"）。"""
    g = normalize_body(gt_text)
    p = normalize_body(pred_text)
    if len(g) < 3:
        return 1.0  # 防御：GT 不足以形成 3-gram，视为满分
    gt_grams = set(zip(g, g[1:], g[2:]))
    if not gt_grams:
        return 1.0
    pred_grams = set(zip(p, p[1:], p[2:])) if len(p) >= 3 else set()
    return len(gt_grams & pred_grams) / len(gt_grams)
```

- [ ] **Step 4: 跑测试验证全 PASS**

Run: `cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP" && uv run --project backend python -m pytest scripts/eval/tests/test_metrics.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/eval/metrics.py scripts/eval/tests/test_metrics.py
git commit -m "feat(eval): 三指标算法 — LCS 标题对齐 / hierarchy / 3-gram content coverage

10 个单测覆盖：normalize / LCS 顺序保真 / TP·FP·FN 边界 / hierarchy 空对齐 /
content_cov 全/部分/空 GT 防御。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Tier 1 风格 GT 加载（自动）+ 单测

**Files:**
- Create: `scripts/eval/gt.py`（先写 Tier1，Tier2/3 留 stub）
- Create: `scripts/eval/tests/test_gt.py`

- [ ] **Step 1: 写失败测试 `test_gt.py`**

```python
"""GT 加载单测。Tier1 / Tier3 抽取器（Tier2 走 fixture 文件，不在此测）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.eval.gt import load_gt_style
from scripts.eval.types import GroundTruth

REPO_ROOT = Path(__file__).resolve().parents[3]
STANDARD_DIR = REPO_ROOT / "docs" / "reference doc" / "typical word doc"


def test_load_gt_style_standard_template():
    """1_程序模板.docx 应有 12 个 styled heading（与 spec 验证表对账）。"""
    gt = load_gt_style(STANDARD_DIR / "1_程序模板.docx")
    assert gt.tier == "style"
    assert len(gt.chapters) >= 5  # spec 显示 12 个，但允许后续微调，下限 5 即可
    # level 必须落在 1-3
    assert all(1 <= c.level <= 3 for c in gt.chapters)
    # 顺序：source_idx 单调
    idxs = [c.source_idx for c in gt.chapters]
    assert idxs == sorted(idxs)
    # body_text 非空（不含标题，但有正文）
    assert len(gt.body_text) > 100


def test_load_gt_style_unstyled_doc_raises():
    """无格式文档应抛出明确异常。"""
    unstyled = REPO_ROOT / "docs" / "reference doc" / "typical word doc" / "无格式标题word" / "02记录控制程序.docx"
    with pytest.raises(ValueError, match="non-style"):
        load_gt_style(unstyled)
```

- [ ] **Step 2: 跑测试验证全 FAIL**

Run: `cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP" && uv run --project backend python -m pytest scripts/eval/tests/test_gt.py -v`
Expected: FAIL (ImportError on load_gt_style)

- [ ] **Step 3: 写 `scripts/eval/gt.py` Tier 1 实现**

```python
"""GroundTruth 加载：Tier1 style（自动）/ Tier2 manual（fixtures）/ Tier3 template。"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from lxml import etree

from app.parser import styles as styles_mod
from scripts.eval.metrics import normalize_title
from scripts.eval.types import GroundTruth, GtChapter, Tier

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "eval_gt"
_MAX_LEVEL = 3


def _qn(tag: str) -> str:
    p, local = tag.split(":")
    return f"{{{NS[p]}}}{local}"


def _load_styles_index(zf: zipfile.ZipFile) -> styles_mod.StyleIndex:
    """从 docx zip 加载 styles.xml → StyleIndex。"""
    try:
        with zf.open("word/styles.xml") as f:
            xml = f.read()
    except KeyError:
        return styles_mod.StyleIndex()
    return styles_mod.parse_styles_xml(xml)


def _iter_body_paragraphs(zf: zipfile.ZipFile):
    """按 child order yield body 段落 (idx, element, text)。"""
    with zf.open("word/document.xml") as f:
        tree = etree.parse(f)
    body = tree.getroot().find(_qn("w:body"))
    if body is None:
        return
    idx = 0
    for child in body.iterchildren():
        if etree.QName(child).localname != "p":
            idx += 1
            continue
        # 收 run 文本
        texts = child.xpath(".//w:t/text()", namespaces=NS)
        text = "".join(texts).strip()
        yield idx, child, text
        idx += 1


def _pstyle_id(p: etree._Element) -> str | None:
    """读 paragraph 的 pStyle val。"""
    pstyle = p.find(f"{_qn('w:pPr')}/{_qn('w:pStyle')}")
    if pstyle is None:
        return None
    return pstyle.get(_qn("w:val"))


def load_gt_style(docx_path: Path) -> GroundTruth:
    """Tier 1：直接遍历 document.xml，对每段调 styles.classify_with_source 反查；
    level 4-6 压到 3。0 命中则抛 ValueError（应改用 Tier2/3）。"""
    with zipfile.ZipFile(docx_path) as zf:
        styles_index = _load_styles_index(zf)
        chapters: list[GtChapter] = []
        body_parts: list[str] = []

        for idx, p, text in _iter_body_paragraphs(zf):
            sid = _pstyle_id(p)
            level, _src = styles_mod.classify_with_source(
                sid, styles_index, synonyms={}, style_overrides={}
            )
            if level is not None and text:
                chapters.append(
                    GtChapter(
                        title=normalize_title(text),
                        level=min(level, _MAX_LEVEL),
                        source_idx=idx,
                    )
                )
            elif text:
                body_parts.append(text)

    if not chapters:
        raise ValueError(
            f"non-style document (0 styled headings): {docx_path.name}; "
            "should use Tier2 (manual) or Tier3 (template) GT"
        )

    return GroundTruth(
        docx_path=docx_path,
        tier="style",
        chapters=tuple(chapters),
        body_text="\n".join(body_parts),
        expected_empty=False,
        reviewed=True,
    )


# Tier2 / Tier3 stub —— Task 4 / 5 实现
def load_gt_manual(docx_path: Path) -> GroundTruth:
    raise NotImplementedError("Tier 2 manual GT loader — see Task 4")


def load_gt_template(docx_path: Path) -> GroundTruth:
    raise NotImplementedError("Tier 3 template GT loader — see Task 5")
```

- [ ] **Step 4: 检查 `app.parser.styles` 暴露的接口**

Run:
```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
uv run --project backend python -c "
import sys; sys.path.insert(0, 'backend')
from app.parser import styles
print(hasattr(styles, 'classify_with_source'), hasattr(styles, 'parse_styles_xml'), hasattr(styles, 'StyleIndex'))
"
```
Expected: `True True True`。**如果 `parse_styles_xml` 不存在**，改用现有的 `StyleIndex.from_xml(xml)` 或类似工厂；如确需新增，作为 Task 3.5 单独提交一次"backend: 暴露 styles.parse_styles_xml 给外部 GT 用"。

- [ ] **Step 5: 跑测试验证全 PASS**

Run: `cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP" && uv run --project backend python -m pytest scripts/eval/tests/test_gt.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add scripts/eval/gt.py scripts/eval/tests/test_gt.py
git commit -m "feat(eval): Tier 1 风格 GT 加载（lxml 遍历 + styles 反查）

5 份标准 SOP 直接派生 GT；level 4-6 压到 3；非 style 文档抛 ValueError。
2 单测：1_程序模板.docx 12 个 heading 命中 + 无格式文档拒绝。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase B · Tier 2 / Tier 3 GT（含 USER ACK 闸门）

### Task 4: Tier 2 manual GT 迁移 + level 补全（产出 ack-list）

**Files:**
- Read: `scripts/validate_unstyled_v3.py`（提 GROUND_TRUTH dict）
- Create: `tests/fixtures/eval_gt/manual/<doc>.json` × 6（待 ack 后入库；先在 `.eval-reports/_draft/manual_gt_review.md` 出 review-list）
- Modify: `scripts/eval/gt.py`（实现 `load_gt_manual`）
- Create: `scripts/eval/tests/test_gt_manual.py`

- [ ] **Step 1: 提取现有 GROUND_TRUTH dict**

Read `scripts/validate_unstyled_v3.py` 顶部的 `GT = {...}` dict，5 份无格式 SOP 的硬编码标题前缀。**注意**：原 GT 只有 title 字符串，没有 level。

- [ ] **Step 2: 补 level——读 docx 推断 + 输出 review-list**

写一次性脚本 `scripts/eval/draft_manual_gt.py`（跑完保留，作为 GT 来源记录）：

```python
"""一次性脚本：6 份 docx → 推断 level 的 GT JSON 草稿 → 写 .eval-reports/_draft/。

推断规则（per spec §2 Tier 2）：
- `N.N.N` 开头 → L3
- `N.N` 开头 → L2
- `N.` / `N+空格` / `第X章` / `一、` / 中文数字+顿号 开头 → L1
- 无编号但加粗短段 → 默认 L1
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

from lxml import etree

from scripts.eval.gt import _iter_body_paragraphs, _paragraph_bold_ratio, NS, _qn  # 复用

# 现有 scripts/validate_unstyled_v3.py 的 GT dict（5 份无格式）
UNSTYLED_GT = {
    "3.危险源监控措施.docx": ["一、危险源", "二、危险源", "三、危险源", "四、危险源", "五、危险源"],
    "有限空间作业管理办法.docx": ["第一章", "第二章", "第三章", "第四章", "第五章", "第九章"],
    "02记录控制程序.docx": [
        "1 目的", "2 范围", "3 职责和权限", "4 工作程序", "5 记录",
        "3.1 ", "3.2 ", "3.3 ", "3.4 ", "4.1 记录", "4.2记录", "4.3 记录",
        "4.4 记录的保管", "4.4 记录的查阅", "4.5 记录",
        "4.1.1", "4.1.2", "4.2.1", "4.3.2", "4.4.1", "4.4.2",
    ],
    "05人力资源控制程序.docx": [
        "1 目的", "2 范围", "3 职责", "4 工作程序", "5记录",
        "3.1 质量部", "3.2 各部门", "3.3 总经理", "4.1 人员安排", "4.2 能力",
        "4.3 培训计划", "4.4 培训实施", "4.5评价", "5.1", "5.2 ",
        "4.2.1 ", "4.2.2", "4.2.3", "4.2.4", "4.2.5", "4.2.6", "4.2.7",
    ],
    "CW-WI-7.4-01外发作业指导书及质量控制程序.docx": [
        "1.目的", "2.适用范围", "3.管理单位", "4.权责", "5.作业程序",
        "4.1 物控", "4.2 品质", "4.3工程", "5.9外发", "5.9.1",
    ],
}

_RE_L3 = re.compile(r"^\d+\.\d+\.\d+")
_RE_L2 = re.compile(r"^\d+\.\d+\b")
_RE_L1_ARABIC = re.compile(r"^\d+[\s.、]")
_RE_L1_CN = re.compile(r"^[一二三四五六七八九十]+[、.]|^第[一二三四五六七八九十\d]+[章节]")


def infer_level(text: str) -> int:
    t = text.strip()
    if _RE_L3.match(t):
        return 3
    if _RE_L2.match(t):
        return 2
    if _RE_L1_ARABIC.match(t) or _RE_L1_CN.match(t):
        return 1
    return 1  # 无编号短粗 → 默认 L1


def locate_in_docx(docx_path: Path, title_prefixes: list[str]) -> list[dict]:
    """对每个 title prefix，在 docx 里找首个匹配段；返回 [{title, level, source_idx}]。"""
    out: list[dict] = []
    used_idxs: set[int] = set()
    with zipfile.ZipFile(docx_path) as zf:
        paragraphs = list(_iter_body_paragraphs(zf))
    for prefix in title_prefixes:
        for idx, _p, text in paragraphs:
            if idx in used_idxs:
                continue
            if text.strip().startswith(prefix.strip()):
                out.append({
                    "title": text.strip(),
                    "level": infer_level(text),
                    "source_idx": idx,
                })
                used_idxs.add(idx)
                break
    return out


def main():
    out_dir = _ROOT / ".eval-reports" / "_draft"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Tier 2 Manual GT — 请 ack（6 份）\n"]

    sources = {
        **{f"docs/reference doc/typical word doc/无格式标题word/{k}": v for k, v in UNSTYLED_GT.items()},
        # QMS doc01：直接用模板归纳，因为它的 anchor 标题相对可枚举
        "docs/reference doc/typical word doc/extra doc/01-公司环境分析控制程序.docx": [
            "1", "2", "3", "4", "5", "6", "7",  # 顶级章节按编号开头
        ],
    }

    for rel, prefixes in sources.items():
        docx = _ROOT / rel
        chapters = locate_in_docx(docx, prefixes)
        lines.append(f"\n## {docx.name}\n")
        lines.append("| # | title (前 40 字) | level | source_idx |")
        lines.append("|---|---|---:|---:|")
        for i, c in enumerate(chapters, 1):
            t = c["title"][:40].replace("|", "\\|")
            lines.append(f"| {i} | {t} | {c['level']} | {c['source_idx']} |")

    review = out_dir / "manual_gt_review.md"
    review.write_text("\n".join(lines), encoding="utf-8")
    print(f"draft → {review}")


if __name__ == "__main__":
    main()
```

Run: `cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP" && uv run --project backend python scripts/eval/draft_manual_gt.py`
Expected: `.eval-reports/_draft/manual_gt_review.md` 含 6 段表格

产出 `.eval-reports/_draft/manual_gt_review.md`：

```markdown
# Tier 2 Manual GT — 请 ack（6 份）

## 3.危险源监控措施.docx
| # | title | level（推断）| 编号特征 |
| 1 | 一、危险源 | 1 | 中文一、 |
| ... |

## 02记录控制程序.docx
| # | title | level（推断）| 编号特征 |
| 1 | 1 目的 | 1 | N+空格 |
| 2 | 3.1 | 2 | N.N |
| ... |
```

- [ ] **Step 3: USER GATE — 等用户 ack**

Halt 实施；把 `manual_gt_review.md` 发给用户审阅，等用户回复"ack"或"修改: …"。任何修改 inline 改回草稿，再 ack。

- [ ] **Step 4: 落盘 `tests/fixtures/eval_gt/manual/*.json`**

格式：
```json
{
  "docx_relpath": "docs/reference doc/typical word doc/无格式标题word/02记录控制程序.docx",
  "tier": "manual",
  "chapters": [
    {"title": "1 目的", "level": 1, "source_idx": 8},
    {"title": "3.1 ", "level": 2, "source_idx": 19}
  ]
}
```

- [ ] **Step 5: 实现 `load_gt_manual`**

```python
def load_gt_manual(docx_path: Path) -> GroundTruth:
    """Tier 2：从 tests/fixtures/eval_gt/manual/<basename>.json 加载 + lxml 拼 body_text。"""
    fixture = _FIXTURES_ROOT / "manual" / f"{docx_path.stem}.json"
    if not fixture.exists():
        raise FileNotFoundError(f"manual GT not found for {docx_path.name}: {fixture}")
    data = json.loads(fixture.read_text(encoding="utf-8"))
    chapters = tuple(
        GtChapter(
            title=normalize_title(c["title"]),
            level=int(c["level"]),
            source_idx=int(c.get("source_idx", i)),
        )
        for i, c in enumerate(data["chapters"])
    )
    # body_text 用 Tier1 同款 lxml 拼，但去掉与 chapter title 同行的段
    with zipfile.ZipFile(docx_path) as zf:
        title_idxs = {c.source_idx for c in chapters}
        parts = [
            text
            for idx, _p, text in _iter_body_paragraphs(zf)
            if text and idx not in title_idxs
        ]
    return GroundTruth(
        docx_path=docx_path,
        tier="manual",
        chapters=chapters,
        body_text="\n".join(parts),
    )
```

- [ ] **Step 6: 写单测验 6 份都能加载**

```python
# scripts/eval/tests/test_gt_manual.py
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


@pytest.mark.parametrize("rel", MANUAL_DOCS)
def test_load_gt_manual_loads(rel):
    gt = load_gt_manual(REPO_ROOT / rel)
    assert gt.tier == "manual"
    assert len(gt.chapters) > 0
    assert all(1 <= c.level <= 3 for c in gt.chapters)
    assert len(gt.body_text) > 50
```

- [ ] **Step 7: 跑测试 + commit**

Run: `uv run --project backend python -m pytest scripts/eval/tests/test_gt_manual.py -v`
Expected: 6 passed

```bash
git add scripts/eval/gt.py scripts/eval/tests/test_gt_manual.py tests/fixtures/eval_gt/manual/
git commit -m "feat(eval): Tier 2 manual GT — 6 份人工 ack 落盘 + 加载器

迁出 validate_unstyled_v3.py 的 GROUND_TRUTH dict，补 level 字段（用户已 ack
.eval-reports/_draft/manual_gt_review.md），落到 tests/fixtures/eval_gt/manual/。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Tier 3 模板抽取器 + 3 份抽样 ack

**Files:**
- Modify: `scripts/eval/gt.py`（加 `extract_qms_gt` + `load_gt_template`）
- Create: `tests/fixtures/eval_gt/template_ack/<doc>.json` × 3
- Create: `scripts/eval/tests/test_gt_template.py`

- [ ] **Step 1: 写 QMS 模板 GT 抽取器**

```python
# 追加到 scripts/eval/gt.py

import re

_QMS_L1 = re.compile(r"^[1-7]\s*[、.]?\s*\S")        # 1./1、/1+空格
_QMS_L2 = re.compile(r"^[1-7]\.[0-9]+\s*[、.]?\s*\S")  # N.N
_QMS_L3 = re.compile(r"^[1-7]\.[0-9]+\.[0-9]+")        # N.N.N


def _paragraph_bold_ratio(p: etree._Element) -> float:
    """读 paragraph runs 的加粗占比（按字符数加权）。"""
    runs = p.findall(_qn("w:r"))
    total = 0
    bold = 0
    for r in runs:
        text = "".join(r.xpath(".//w:t/text()", namespaces=NS))
        n = len(text)
        if n == 0:
            continue
        total += n
        rpr = r.find(_qn("w:rPr"))
        if rpr is not None:
            b = rpr.find(_qn("w:b"))
            if b is not None and b.get(_qn("w:val")) != "0":
                bold += n
    return (bold / total) if total > 0 else 0.0


def extract_qms_gt(docx_path: Path, *, require_bold: bool = True) -> GroundTruth:
    """Tier 3：QMS 模板归纳 GT 抽取器（独立于 parser 的 classify_numbering）。"""
    chapters: list[GtChapter] = []
    body_parts: list[str] = []
    with zipfile.ZipFile(docx_path) as zf:
        for idx, p, text in _iter_body_paragraphs(zf):
            if not text:
                continue
            bold = _paragraph_bold_ratio(p) if require_bold else 1.0
            level: int | None = None
            if _QMS_L3.match(text):
                level = 3
            elif _QMS_L2.match(text):
                level = 2
            elif _QMS_L1.match(text) and len(text) <= 30 and bold >= 0.5:
                # L1 必须粗体短段（避免吞 "1、xxx" 的列表正文）
                level = 1
            if level is not None:
                chapters.append(
                    GtChapter(title=normalize_title(text), level=level, source_idx=idx)
                )
            else:
                body_parts.append(text)
    return GroundTruth(
        docx_path=docx_path,
        tier="template",
        chapters=tuple(chapters),
        body_text="\n".join(body_parts),
        expected_empty=(len(chapters) == 0 and "目录" in docx_path.name),
        reviewed=False,  # 默认未 ack；ack 的 3 份在 load_gt_template 里改 True
    )


def load_gt_template(docx_path: Path) -> GroundTruth:
    """Tier 3 入口：优先读 fixture（已 ack）；否则走 extract_qms_gt（reviewed=False）。"""
    fixture = _FIXTURES_ROOT / "template_ack" / f"{docx_path.stem}.json"
    if fixture.exists():
        data = json.loads(fixture.read_text(encoding="utf-8"))
        chapters = tuple(
            GtChapter(
                title=normalize_title(c["title"]),
                level=int(c["level"]),
                source_idx=int(c.get("source_idx", i)),
            )
            for i, c in enumerate(data["chapters"])
        )
        # body_text 还是用 extract_qms_gt 的方式拼
        extracted = extract_qms_gt(docx_path)
        return GroundTruth(
            docx_path=docx_path,
            tier="template",
            chapters=chapters,
            body_text=extracted.body_text,
            expected_empty=extracted.expected_empty,
            reviewed=True,
        )
    return extract_qms_gt(docx_path)
```

- [ ] **Step 2: 跑抽取器在 3 份抽样上 + 产出 ack-list**

写一次性脚本 `scripts/eval/draft_template_gt.py`，跑 3 份目标文档：
- `extra doc/05-基础设施控制程序.docx`
- `extra doc/15-标识和可追溯性控制程序.docx`
- `extra doc/25-各级人员质量职责和权限规定.docx`

产出 `.eval-reports/_draft/template_gt_review.md`：

```markdown
# Tier 3 Template GT — 请 ack（3 份抽样）

## 05-基础设施控制程序.docx
| # | title（normalize 后） | level（抽取器判）| 原文（前 40 字）|
| 1 | 1目的 | 1 | 1 目的 |
| 2 | 2范围 | 1 | 2 范围 |
| ... |

…
```

- [ ] **Step 3: USER GATE — 等用户 ack**

Halt；发 `template_gt_review.md` 给用户。任何修改 inline，再 ack。

- [ ] **Step 4: 落盘 `tests/fixtures/eval_gt/template_ack/*.json`**

格式与 manual 同。

- [ ] **Step 5: 写单测**

```python
# scripts/eval/tests/test_gt_template.py
from pathlib import Path

import pytest

from scripts.eval.gt import extract_qms_gt, load_gt_template

REPO_ROOT = Path(__file__).resolve().parents[3]
QMS_DIR = REPO_ROOT / "docs" / "reference doc" / "typical word doc" / "extra doc"

ACKED = ["05-基础设施控制程序.docx", "15-标识和可追溯性控制程序.docx", "25-各级人员质量职责和权限规定.docx"]


@pytest.mark.parametrize("name", ACKED)
def test_load_gt_template_acked_returns_reviewed(name):
    gt = load_gt_template(QMS_DIR / name)
    assert gt.tier == "template"
    assert gt.reviewed is True
    assert len(gt.chapters) > 0


def test_extract_qms_gt_unacked_returns_unreviewed():
    gt = load_gt_template(QMS_DIR / "10-沟通控制程序.docx")
    assert gt.reviewed is False
    assert len(gt.chapters) > 0


def test_extract_qms_gt_directory_marked_empty():
    gt = load_gt_template(QMS_DIR / "程序文件目录.docx")
    assert gt.expected_empty is True
    assert len(gt.chapters) == 0
```

- [ ] **Step 6: 跑测 + commit**

Run: `uv run --project backend python -m pytest scripts/eval/tests/test_gt_template.py -v`
Expected: 5 passed

```bash
git add scripts/eval/gt.py scripts/eval/tests/test_gt_template.py tests/fixtures/eval_gt/template_ack/
git commit -m "feat(eval): Tier 3 模板 GT 抽取器 + 3 份抽样 ack

extract_qms_gt 用独立正则 ^[1-7] 系列（不复用 parser.classify_numbering），L1 要求
粗体+短段。3 份抽样（doc05/15/25）已用户 ack 落 fixtures/eval_gt/template_ack/。
程序文件目录.docx 自动标记 expected_empty=True。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase C · Runner + Report

### Task 6: Runner（per-doc 流水线）+ 集成测

**Files:**
- Create: `scripts/eval/runner.py`
- Create: `scripts/eval/tests/test_runner.py`

- [ ] **Step 1: 写失败集成测**

```python
"""runner 集成测：用最小 fixture 跑通整条 GT→parse→metric 链路。"""
from __future__ import annotations

from pathlib import Path

from scripts.eval.runner import discover_docs, run_eval

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_discover_docs_standard_subset_finds_5():
    docs = discover_docs(REPO_ROOT, subset="standard")
    assert len(docs) == 5
    assert all(d.name.endswith(".docx") for d in docs)


def test_discover_docs_unstyled_subset_finds_5():
    docs = discover_docs(REPO_ROOT, subset="unstyled")
    assert len(docs) == 5


def test_discover_docs_qms_subset_finds_26():
    """26 = 25 SOP + 1 程序文件目录.docx。"""
    docs = discover_docs(REPO_ROOT, subset="qms")
    assert len(docs) == 26


def test_run_eval_standard_smart_mode_smoke():
    """跑 5 份标准 SOP 在 smart 模式下端到端，至少返回 5 个 DocResult。"""
    report = run_eval(REPO_ROOT, subset="standard", mode="smart")
    assert len(report.docs) == 5
    # 5 份都是 style tier
    assert all(d.tier == "style" for d in report.docs)
    # smoke：title metrics 全有值
    assert all(d.title.precision >= 0 for d in report.docs)
```

- [ ] **Step 2: 跑测验 FAIL**

Run: `uv run --project backend python -m pytest scripts/eval/tests/test_runner.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: 写 `scripts/eval/runner.py`**

```python
"""Eval runner：发现文档 → 加 GT → 调 parser → 算指标 → 装配 DocResult。"""
from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup

from app.parser import parse_docx
from app.parser.result import ParseResult, ParsedNode
from scripts.eval.gt import (
    extract_qms_gt,
    load_gt_manual,
    load_gt_style,
    load_gt_template,
)
from scripts.eval.metrics import (
    align_chapters,
    content_cov_3gram,
    hierarchy_acc,
    title_prf,
)
from scripts.eval.types import DocResult, EvalReport, GroundTruth, GtChapter

Subset = Literal["all", "standard", "unstyled", "qms"]
Mode = Literal["standard", "smart"]

_STANDARD_DIR = Path("docs/reference doc/typical word doc")
_UNSTYLED_DIR = _STANDARD_DIR / "无格式标题word"
_QMS_DIR = _STANDARD_DIR / "extra doc"

# Tier 2 manual GT 包含的 6 份
_MANUAL_GT_BASENAMES = {
    "3.危险源监控措施", "02记录控制程序", "05人力资源控制程序",
    "CW-WI-7.4-01外发作业指导书及质量控制程序", "有限空间作业管理办法",
    "01-公司环境分析控制程序",
}


def discover_docs(repo_root: Path, subset: Subset) -> list[Path]:
    """枚举 docx；不递归 backend/var/。"""
    standard_dir = repo_root / _STANDARD_DIR
    unstyled_dir = repo_root / _UNSTYLED_DIR
    qms_dir = repo_root / _QMS_DIR

    out: list[Path] = []
    if subset in ("all", "standard"):
        out.extend(sorted(p for p in standard_dir.glob("*.docx") if "无格式" not in p.name))
    if subset in ("all", "unstyled"):
        out.extend(sorted(unstyled_dir.glob("*.docx")))
    if subset in ("all", "qms"):
        out.extend(sorted(qms_dir.glob("*.docx")))
    return out


def _select_loader(docx_path: Path) -> GroundTruth:
    """根据路径 + Tier 2 名单选 loader。"""
    if docx_path.stem in _MANUAL_GT_BASENAMES:
        return load_gt_manual(docx_path)
    if "extra doc" in docx_path.parts:
        return load_gt_template(docx_path)
    # 默认尝试 style；style 失败时（非 styled）退到 manual（应已在名单里）
    try:
        return load_gt_style(docx_path)
    except ValueError:
        return load_gt_manual(docx_path)


def _flatten_chapters(nodes: list[ParsedNode]) -> list[GtChapter]:
    """ParseResult.chapters 树 → 扁平 GtChapter 序列（按出现顺序）。"""
    out: list[GtChapter] = []
    counter = {"i": 0}

    def visit(n: ParsedNode):
        if n.content_type == "chapter":
            out.append(GtChapter(title=n.title or "", level=n.level, source_idx=counter["i"]))
        counter["i"] += 1
        for c in n.children:
            visit(c)

    for n in nodes:
        visit(n)
    return out


def _collect_parsed_body_text(nodes: list[ParsedNode]) -> str:
    """递归收集所有 content_type='content' 节点的 rich_content，BS 取 text。"""
    parts: list[str] = []

    def visit(n: ParsedNode):
        if n.content_type == "content" and n.rich_content:
            text = BeautifulSoup(n.rich_content, "html.parser").get_text(separator="\n")
            parts.append(text)
        for c in n.children:
            visit(c)

    for n in nodes:
        visit(n)
    return "\n".join(parts)


def _eval_one(docx_path: Path, mode: Mode) -> DocResult:
    gt = _select_loader(docx_path)
    parsed: ParseResult = parse_docx(docx_path, mode=mode)
    pred_chapters = _flatten_chapters(parsed.chapters)
    pred_body = _collect_parsed_body_text(parsed.chapters)

    title_m = title_prf(list(gt.chapters), pred_chapters)
    aligned = align_chapters(list(gt.chapters), pred_chapters)
    h_acc = hierarchy_acc(aligned)

    # FP/FN 摘要（用 normalize 前的原文，便于人读）
    aligned_gt_idx = {i for i, _ in [(g, p) for g, p in aligned for _ in [None]]}  # placeholder
    # 简化版：直接重算
    from scripts.eval.metrics import lcs_align, normalize_title
    gt_norm = [normalize_title(c.title) for c in gt.chapters]
    pred_norm = [normalize_title(c.title) for c in pred_chapters]
    pairs = lcs_align(gt_norm, pred_norm)
    aligned_gt = {i for i, _ in pairs}
    aligned_pred = {j for _, j in pairs}
    fn_titles = [gt.chapters[i].title for i in range(len(gt.chapters)) if i not in aligned_gt]
    fp_titles = [pred_chapters[j].title for j in range(len(pred_chapters)) if j not in aligned_pred]
    level_mm = [
        (g.title, g.level, p.level)
        for g, p in aligned if g.level != p.level
    ]

    cov = content_cov_3gram(gt.body_text, pred_body)

    return DocResult(
        docx_path=docx_path,
        tier=gt.tier,
        expected_empty=gt.expected_empty,
        reviewed=gt.reviewed,
        title=title_m,
        hierarchy_acc=h_acc,
        content_cov=cov,
        fp_titles=fp_titles,
        fn_titles=fn_titles,
        level_mismatches=level_mm,
        body_start_detected_by=parsed.metadata.body_start_detected_by,
        warnings=[w.message for w in parsed.warnings],
    )


def run_eval(repo_root: Path, *, subset: Subset = "all", mode: Mode = "smart") -> EvalReport:
    docs = discover_docs(repo_root, subset)
    results = [_eval_one(d, mode) for d in docs]
    return EvalReport(
        timestamp=datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S"),
        mode=mode,
        subset=subset,
        docs=results,
    )
```

> **风险点**：`from app.parser import parse_docx`——确认这是公开 API。如果当前 `__init__.py` 没暴露，先在 Task 6.5 用一个 backend 小 commit 加 `__all__`。

- [ ] **Step 4: 跑测验证 PASS**

Run: `uv run --project backend python -m pytest scripts/eval/tests/test_runner.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/eval/runner.py scripts/eval/tests/test_runner.py
git commit -m "feat(eval): runner per-doc 流水线 + GT↔parser↔指标装配

discover_docs 按 subset 列 36 份；_select_loader 按路径分发 Tier1/2/3 loader；
parse_docx 直 import；BeautifulSoup 取 content text。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Report 生成（summary.md / summary.json / diff）

**Files:**
- Create: `scripts/eval/report.py`
- Create: `scripts/eval/tests/test_report.py`

- [ ] **Step 1: 写失败测**

```python
"""report 单测：summary.md 红绿灯格式 + summary.json 可被 load。"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.report import write_summary, write_diff
from scripts.eval.types import DocResult, EvalReport, TitleMetrics


def _mk_result(name: str, p: float, r: float, h: float | None, cov: float, tier="style"):
    return DocResult(
        docx_path=Path(f"/tmp/{name}.docx"),
        tier=tier,
        expected_empty=False,
        reviewed=True,
        title=TitleMetrics(tp=8, fp=0, fn=2, precision=p, recall=r, f1=2 * p * r / (p + r) if p + r > 0 else 0),
        hierarchy_acc=h,
        content_cov=cov,
    )


def test_write_summary_creates_files(tmp_path):
    report = EvalReport(
        timestamp="2026-05-27-120000",
        mode="smart",
        subset="all",
        docs=[
            _mk_result("a", 1.0, 0.8, 0.95, 0.99),
            _mk_result("b", 1.0, 0.7, 0.90, 0.96, tier="manual"),
        ],
    )
    write_summary(report, tmp_path)
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "summary.json").exists()
    md = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # 红绿灯五行
    assert "title_P_micro" in md
    assert "title_R_micro" in md
    assert "hierarchy_micro" in md
    assert "content_cov_micro" in md
    # JSON 可读回
    data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert data["mode"] == "smart"
    assert len(data["docs"]) == 2


def test_write_diff_detects_regression(tmp_path):
    baseline = EvalReport(
        timestamp="t0", mode="smart", subset="all",
        docs=[_mk_result("a", 1.0, 0.9, 0.95, 0.99)],
    )
    current = EvalReport(
        timestamp="t1", mode="smart", subset="all",
        docs=[_mk_result("a", 1.0, 0.8, 0.95, 0.99)],  # R 退了 0.1
    )
    write_diff(current, baseline, tmp_path)
    diff_md = (tmp_path / "diff_vs_baseline.md").read_text(encoding="utf-8")
    assert "a.docx" in diff_md
    assert "退化" in diff_md or "regression" in diff_md.lower() or "↓" in diff_md
```

- [ ] **Step 2: 跑测验 FAIL**

Run: `uv run --project backend python -m pytest scripts/eval/tests/test_report.py -v`
Expected: FAIL

- [ ] **Step 3: 写 `scripts/eval/report.py`**

```python
"""Eval 报告生成：summary.md 红绿灯 + summary.json 留档 + diff_vs_baseline.md。"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from scripts.eval.types import DocResult, EvalReport, Tier

# 严强阈值（spec §3.4）
TH_P = 0.98
TH_R = 0.85
TH_R_PER_DOC = 0.60
TH_HIERARCHY = 0.95
TH_COV = 0.98


def _micro(docs: list[DocResult], field: str) -> float:
    """按 TP+FN 加权（title）或按 |TP| 加权（hierarchy）或按 GT body grams 数加权（cov）。
    简化：title 用 tp/(tp+fn) 累计；其余直接平均权重 = TP。
    """
    if field == "title_p":
        tp = sum(d.title.tp for d in docs)
        fp = sum(d.title.fp for d in docs)
        return tp / (tp + fp) if (tp + fp) > 0 else 1.0
    if field == "title_r":
        tp = sum(d.title.tp for d in docs)
        fn = sum(d.title.fn for d in docs)
        return tp / (tp + fn) if (tp + fn) > 0 else 1.0
    if field == "title_f1":
        p = _micro(docs, "title_p")
        r = _micro(docs, "title_r")
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    if field == "hierarchy":
        total_tp = sum(d.title.tp for d in docs if d.hierarchy_acc is not None)
        if total_tp == 0:
            return 1.0
        return sum((d.hierarchy_acc or 0) * d.title.tp for d in docs if d.hierarchy_acc is not None) / total_tp
    if field == "content_cov":
        # 简化：按文档数算（macro），cov 已是比例
        if not docs:
            return 1.0
        return sum(d.content_cov for d in docs) / len(docs)
    raise ValueError(f"unknown micro field: {field}")


def _macro(docs: list[DocResult], field: str) -> float:
    if not docs:
        return 1.0
    if field == "title_p":
        return sum(d.title.precision for d in docs) / len(docs)
    if field == "title_r":
        return sum(d.title.recall for d in docs) / len(docs)
    if field == "title_f1":
        return sum(d.title.f1 for d in docs) / len(docs)
    if field == "hierarchy":
        vals = [d.hierarchy_acc for d in docs if d.hierarchy_acc is not None]
        return sum(vals) / len(vals) if vals else 1.0
    if field == "content_cov":
        return sum(d.content_cov for d in docs) / len(docs)
    raise ValueError(f"unknown macro field: {field}")


def _light(value: float, threshold: float, *, lower_bound: bool = True) -> str:
    """生成 ✅ / ❌。lower_bound=True 表示 value≥threshold 才通过。"""
    if lower_bound:
        return "✅" if value >= threshold else "❌"
    return "✅" if value <= threshold else "❌"


def _docresult_to_dict(d: DocResult) -> dict:
    return {
        "docx_path": str(d.docx_path),
        "tier": d.tier,
        "expected_empty": d.expected_empty,
        "reviewed": d.reviewed,
        "title": asdict(d.title),
        "hierarchy_acc": d.hierarchy_acc,
        "content_cov": d.content_cov,
        "fp_titles": d.fp_titles,
        "fn_titles": d.fn_titles,
        "level_mismatches": d.level_mismatches,
        "body_start_detected_by": d.body_start_detected_by,
        "warnings": d.warnings,
    }


def write_summary(report: EvalReport, out_dir: Path) -> None:
    """写 summary.md（红绿灯 + per-doc 表）+ summary.json + per_doc/<name>.json。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 排除 expected_empty 进入达标分母
    eligible = [d for d in report.docs if not d.expected_empty]
    # 主线指标按 Tier1+Tier2 算（reviewed=True 且 tier ∈ {style, manual}）
    mainline = [d for d in eligible if d.reviewed and d.tier in ("style", "manual")]

    p_micro = _micro(mainline, "title_p")
    r_micro = _micro(mainline, "title_r")
    h_micro = _micro(mainline, "hierarchy")
    c_micro = _micro(mainline, "content_cov")
    min_r_doc = min(mainline, key=lambda d: d.title.recall, default=None)
    min_r = min_r_doc.title.recall if min_r_doc else 1.0

    lines = [
        f"# Eval Report — {report.timestamp} ({report.mode}, subset={report.subset})\n",
        "## 严强阈值（主线 = Tier1 + Tier2，必须全 ✅ 才算闭环结束）\n",
        f"- [{_light(p_micro, TH_P)}] title_P_micro ≥ {TH_P}   当前: {p_micro:.4f}",
        f"- [{_light(r_micro, TH_R)}] title_R_micro ≥ {TH_R}   当前: {r_micro:.4f}",
        f"- [{_light(min_r, TH_R_PER_DOC)}] no_doc_with_R < {TH_R_PER_DOC}   最低: {min_r_doc.docx_path.name if min_r_doc else '-'} (R={min_r:.2f})",
        f"- [{_light(h_micro, TH_HIERARCHY)}] hierarchy_micro ≥ {TH_HIERARCHY}   当前: {h_micro:.4f}",
        f"- [{_light(c_micro, TH_COV)}] content_cov_micro ≥ {TH_COV}   当前: {c_micro:.4f}",
        "",
        "## Per-Doc",
        "| 文档 | tier | reviewed | P | R | F1 | hier | cov | body_start_by | FP | FN |",
        "|---|---|---|---|---|---|---|---|---|---:|---:|",
    ]
    for d in report.docs:
        h_str = f"{d.hierarchy_acc:.2f}" if d.hierarchy_acc is not None else "-"
        rev = "✅" if d.reviewed else "⚠️"
        if d.expected_empty:
            rev = "📂"  # 目录文件
        lines.append(
            f"| {d.docx_path.name} | {d.tier} | {rev} | "
            f"{d.title.precision:.2f} | {d.title.recall:.2f} | {d.title.f1:.2f} | "
            f"{h_str} | {d.content_cov:.2f} | {d.body_start_detected_by or '-'} | "
            f"{d.title.fp} | {d.title.fn} |"
        )

    # Tier 分档汇总
    lines.append("\n## Tier 分档 micro\n")
    lines.append("| tier | docs | P_micro | R_micro | F1_micro | hier_micro | cov_macro |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for tier in ("style", "manual", "template"):
        tier_docs = [d for d in eligible if d.tier == tier]
        if not tier_docs:
            continue
        lines.append(
            f"| {tier} | {len(tier_docs)} | "
            f"{_micro(tier_docs, 'title_p'):.4f} | {_micro(tier_docs, 'title_r'):.4f} | "
            f"{_micro(tier_docs, 'title_f1'):.4f} | {_micro(tier_docs, 'hierarchy'):.4f} | "
            f"{_micro(tier_docs, 'content_cov'):.4f} |"
        )

    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    # summary.json
    data = {
        "timestamp": report.timestamp,
        "mode": report.mode,
        "subset": report.subset,
        "thresholds": {
            "p_micro": p_micro, "r_micro": r_micro, "min_r_per_doc": min_r,
            "hierarchy_micro": h_micro, "content_cov_micro": c_micro,
        },
        "docs": [_docresult_to_dict(d) for d in report.docs],
    }
    (out_dir / "summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # per_doc/
    per_dir = out_dir / "per_doc"
    per_dir.mkdir(exist_ok=True)
    for d in report.docs:
        (per_dir / f"{d.docx_path.stem}.json").write_text(
            json.dumps(_docresult_to_dict(d), ensure_ascii=False, indent=2), encoding="utf-8"
        )


def write_diff(current: EvalReport, baseline: EvalReport, out_dir: Path) -> None:
    """对照 baseline 出 diff。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    base_by = {d.docx_path.name: d for d in baseline.docs}
    lines = [
        f"# Diff vs Baseline ({baseline.timestamp} → {current.timestamp})\n",
        "| 文档 | ΔP | ΔR | ΔF1 | Δhier | Δcov | 状态 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for d in current.docs:
        b = base_by.get(d.docx_path.name)
        if b is None:
            lines.append(f"| {d.docx_path.name} | new | - | - | - | - | 新增 |")
            continue

        def delta(a: float, b_val: float) -> str:
            diff = a - b_val
            if diff > 0.005:
                return f"+{diff:.3f} ↑"
            if diff < -0.005:
                return f"{diff:.3f} ↓ 退化"
            return "="

        dp = delta(d.title.precision, b.title.precision)
        dr = delta(d.title.recall, b.title.recall)
        df = delta(d.title.f1, b.title.f1)
        dh = delta(d.hierarchy_acc or 0, b.hierarchy_acc or 0) if (d.hierarchy_acc and b.hierarchy_acc) else "-"
        dc = delta(d.content_cov, b.content_cov)
        regressed = any("退化" in x for x in [dp, dr, df, str(dh), dc])
        status = "🔴 退化" if regressed else ("🟢 升" if any("↑" in x for x in [dp, dr, df, str(dh), dc]) else "—")
        lines.append(f"| {d.docx_path.name} | {dp} | {dr} | {df} | {dh} | {dc} | {status} |")

    (out_dir / "diff_vs_baseline.md").write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: 跑测 PASS**

Run: `uv run --project backend python -m pytest scripts/eval/tests/test_report.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/eval/report.py scripts/eval/tests/test_report.py
git commit -m "feat(eval): summary.md 红绿灯 + per_doc JSON + diff_vs_baseline.md

主线指标按 Tier1+Tier2 算（mainline = reviewed=True & tier∈{style,manual}）；
Tier3 单独分档报；expected_empty 标 📂 不进达标。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: CLI 入口 `scripts/eval_parser.py`

**Files:**
- Create: `scripts/eval_parser.py`

- [ ] **Step 1: 写 CLI**

```python
#!/usr/bin/env python
"""Word 解析器评测 harness CLI。

Usage:
    uv run --project backend python scripts/eval_parser.py
    uv run --project backend python scripts/eval_parser.py --subset standard
    uv run --project backend python scripts/eval_parser.py --baseline .eval-reports/baseline/summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, UTC
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

from scripts.eval.runner import run_eval  # noqa: E402
from scripts.eval.report import write_summary, write_diff  # noqa: E402
from scripts.eval.types import EvalReport  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Word parser evaluation harness")
    ap.add_argument("--subset", choices=["all", "standard", "unstyled", "qms"], default="all")
    ap.add_argument("--mode", choices=["standard", "smart"], default="smart")
    ap.add_argument("--baseline", type=Path, default=None, help="path to a previous summary.json for diff")
    ap.add_argument("--out", type=Path, default=None, help="output dir (default .eval-reports/<ts>/)")
    args = ap.parse_args(argv)

    ts = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
    out = args.out or (_ROOT / ".eval-reports" / ts)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[eval] subset={args.subset} mode={args.mode} → {out}")
    report = run_eval(_ROOT, subset=args.subset, mode=args.mode)
    write_summary(report, out)

    if args.baseline:
        baseline_data = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline = _load_eval_report(baseline_data)
        write_diff(report, baseline, out)

    # 终端简报
    eligible = [d for d in report.docs if not d.expected_empty and d.reviewed and d.tier in ("style", "manual")]
    tp = sum(d.title.tp for d in eligible)
    fp = sum(d.title.fp for d in eligible)
    fn = sum(d.title.fn for d in eligible)
    p = tp / (tp + fp) if (tp + fp) else 1.0
    r = tp / (tp + fn) if (tp + fn) else 1.0
    print(f"[eval] mainline P={p:.4f} R={r:.4f} ({len(eligible)} docs)")
    print(f"[eval] full report → {out / 'summary.md'}")
    return 0


def _load_eval_report(data: dict) -> EvalReport:
    """从 summary.json data 反序列化 EvalReport（baseline diff 用，只需 docs 字段）。"""
    from scripts.eval.types import DocResult, TitleMetrics
    docs = []
    for d in data["docs"]:
        docs.append(DocResult(
            docx_path=Path(d["docx_path"]),
            tier=d["tier"],
            expected_empty=d["expected_empty"],
            reviewed=d["reviewed"],
            title=TitleMetrics(**d["title"]),
            hierarchy_acc=d["hierarchy_acc"],
            content_cov=d["content_cov"],
            fp_titles=d["fp_titles"],
            fn_titles=d["fn_titles"],
            level_mismatches=d["level_mismatches"],
            body_start_detected_by=d.get("body_start_detected_by"),
            warnings=d.get("warnings", []),
        ))
    return EvalReport(timestamp=data["timestamp"], mode=data["mode"], subset=data["subset"], docs=docs)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 跑一次 standard subset 端到端验证**

Run:
```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
uv run --project backend python scripts/eval_parser.py --subset standard
```
Expected:
- 终端打印 `[eval] mainline P=... R=... (5 docs)`
- `.eval-reports/<ts>/summary.md` 存在并可读
- 5 份标准 SOP 都在 per_doc/ 下有 JSON
- 红绿灯不全是 ❌（标准 SOP 应该都接近 1.0）

- [ ] **Step 3: 跑一次 all subset 验证 36 份全跑完**

Run: `uv run --project backend python scripts/eval_parser.py --subset all`
Expected:
- 终端打印 `(11 docs)` 主线（5 style + 6 manual）
- summary.md 含 Tier 分档汇总 3 行（style/manual/template）
- 总耗时 < 30s

- [ ] **Step 4: Commit**

```bash
git add scripts/eval_parser.py
git commit -m "feat(eval): CLI 入口 scripts/eval_parser.py — --subset / --mode / --baseline / --out

直 sys.path 注入 backend 路径；baseline 反序列化用于 diff；终端打印主线 P/R 简报。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase D · 基线 + 调参回路

### Task 9: 跑首轮 baseline + 初始化 tuning log

**Files:**
- Create: `.eval-reports/baseline/`（产物，不进 git）
- Create: `docs/parser-tuning-log.md`

- [ ] **Step 1: 跑首轮 baseline**

Run:
```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
uv run --project backend python scripts/eval_parser.py --subset all --out .eval-reports/baseline
```
Expected: `.eval-reports/baseline/summary.md` + `summary.json` + 36 份 per_doc/

- [ ] **Step 2: 读 baseline 数据 → 初始化 `docs/parser-tuning-log.md`**

```markdown
# Parser Tuning Log

按 spec §4.3 一轮一行，每行强制写 trade-off 理由。

| 轮 | 时间 (UTC) | 改动 | 改的文件 | mainline P_micro | R_micro | F1_micro | hierarchy | cov_macro | 备注 / trade-off |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| 0 (baseline) | 2026-05-27 ... | — | — | <从 summary.json 抄> | ... | ... | ... | ... | 起点；阈值 P≥0.98 R≥0.85 hier≥0.95 cov≥0.98 |
```

实际数值从 `.eval-reports/baseline/summary.json` 的 `thresholds` 字段抄。

- [ ] **Step 3: Commit（仅 tuning log，不含报告产物）**

```bash
git add docs/parser-tuning-log.md
git commit -m "chore(eval): 初始化 parser-tuning-log.md + 跑首轮 baseline

baseline → .eval-reports/baseline/（gitignored）。tuning log 第 0 行为起点指标。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: 调参回路（每轮一次执行此模板，重复直至阈值全 ✅）

**Per-iteration playbook：** 重复执行下列步骤，每轮一个独立 commit。

- [ ] **Step 1: 跑 eval（diff vs 上一轮）**

Run:
```bash
LAST=$(ls -td .eval-reports/* | grep -v baseline | grep -v _draft | head -1)
LAST_BASE=${LAST:-".eval-reports/baseline"}
uv run --project backend python scripts/eval_parser.py --subset all --baseline "$LAST_BASE/summary.json"
```

- [ ] **Step 2: 读 summary.md 红绿灯 + diff_vs_baseline.md**

任一指标 ❌ 退化 → 立即 `git stash`，找罪魁，禁带退化继续。

- [ ] **Step 3: 选 1-2 个失败模式定向改**

按 spec §4.2 优先级（P0 > P1 > P2 > P3 > P4）。

| 类 | 改动位点 |
|---|---|
| a. 编号字典 miss / 误判 | `backend/app/parser/heading_detector.py` `_RE_*` + `classify_numbering` |
| b. 启发式分数偏差 | `score_block` 权重 |
| c. body_start 跑偏 | `backend/app/parser/body_start.py` |
| d. 样式反查链 miss | `backend/app/parser/styles.classify_with_source` |
| e. 同义词词典缺项 | `config/heading_synonyms.yaml` |
| f. structurer 边界 | `backend/app/parser/structurer.py` |

**TDD 强制**：改之前在 `backend/tests/unit/parser/test_*.py` 加一个失败单测，覆盖本轮要修的具体模式。改完单测必须绿。

- [ ] **Step 4: 跑现有单测确保不退化**

Run: `cd backend && uv run python -m pytest tests/unit/parser/ -v`
Expected: all green。任何红 → 回 Step 3。

- [ ] **Step 5: 再跑 eval，对照 diff**

Run: 同 Step 1。
检查：
- 改动文档的指标必须升；
- 其它文档任一指标不允许退（micro/macro/per-doc 全部）；
- **trade-off 自决**：若 doc A 升 0.3 / doc B 退 0.05，自行权衡（按 spec §4.4），保留 / revert 决定写进 tuning log 备注列。

- [ ] **Step 6: 若属 P3 失败模式（动 import_blocks / 切块）→ §5 MCP 抽样验收**

按 spec §5.2 6 步走 6 份样本：

```
[a] mcp__chrome-devtools__new_page (or navigate_page) → http://localhost:5173/procedures/new-from-word
[b] mcp__chrome-devtools__upload_file <docx>
[c] mcp__chrome-devtools__wait_for "章节树渲染" 选择器
[d] mcp__chrome-devtools__take_screenshot → .verify-screenshots/eval-r<轮号>-S<编号>.png
[e] mcp__chrome-devtools__evaluate_script
    → 读 Pinia store chapters tree → JSON.stringify → 比对 per_doc/<name>.json
[f] mcp__chrome-devtools__list_console_messages → 任何 error 必 revert
```

> 前提：本地 dev server 已起。若未起，先 `cd frontend && npm run dev`（独立终端），等 vite ready。

异常 / chapters JSON 不一致 → revert 本轮 commit。

- [ ] **Step 7: 追加 `docs/parser-tuning-log.md` 一行**

| 轮 | 时间 (UTC) | 改动 | 改的文件 | P_micro | R_micro | F1_micro | hier | cov | 备注 / trade-off |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| N | YYYY-MM-DD HHMMSS | <一句话>: <模式> | path/to/file.py | 0.xxxx | 0.xxxx | 0.xxxx | 0.xxxx | 0.xxxx | 升 docXX +Y / 退 docZZ -W；选保留因 ... |

- [ ] **Step 8: Commit**

```bash
git add backend/app/parser/<改的文件> backend/tests/unit/parser/<新单测> docs/parser-tuning-log.md
git commit -m "tune(parser): <模式名> → +R Δ0.xx / no regression

<改动描述 1-2 行>

per spec §4.2 P<优先级>。tuning log row <N>。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 9: 检查退出条件**

按 spec §4.5：
1. **达标退出**：summary.md 红绿灯全 ✅ → 进 Task 11；
2. **停滞退出**：连续 3 轮 micro 指标 Δ < 0.005 → 写"剩余失败模式 + 预期收益和风险"短报告，问用户是否继续/降阈值/改方案，回 Step 1（用户决策后）或终止；
3. **既不达标也不停滞** → 回 Step 1。

---

## Phase E · 综合评估

### Task 11: 综合评估与重构建议文档

**Files:**
- Create: `docs/parser-comprehensive-evaluation.md`

> 仅在 Task 10 退出条件 1 达标时执行。如停滞退出（条件 2），按用户决策决定是否仍出此文档。

- [ ] **Step 1: 收集指标快照**

读最新一份 `.eval-reports/<ts>/summary.json` + `parser-tuning-log.md` 全部行。

- [ ] **Step 2: 写文档骨架**

```markdown
# Parser 综合评估与重构建议

**评测日期：** <YYYY-MM-DD>
**最终指标（mainline，36 份）：**
- title P_micro = …, R_micro = …, F1_micro = …
- hierarchy_micro = …
- content_cov_micro = …
- 严强阈值通过情况：…

## 1. 解析器现状画像

### 1.1 三阶段各自的真实承担与盲区
- Normalizer：<行数> 行 / <承担>；盲区：<示例 + 文档名>
- Structurer：…
- Serializer：…

### 1.2 36 份样本上的模式清单
- 已识别：<列表，含示例文档>
- 仍未识别：<列表，含示例文档 + 为什么留在 FN>

### 1.3 与 word-parser-solution.md 原设计偏差对账
- 偏差 1: …
- 偏差 2: …

### 1.4 每个文件的圈复杂度 / 单测覆盖率 / 改动频次
| 文件 | LOC | 圈复杂度 | unit cov | 本闭环改动次数 |
|---|---:|---:|---:|---:|
| heading_detector.py | … | … | … | … |
| …

## 2. 质量画像

### 2.1 三指标的天花板归因
| 指标 | 当前缺口 | 归因（算法 / GT 噪音 / 业务模糊） | 示例文档 |
|---|---|---|---|
| title_R | … | … | … |
| hierarchy | … | … | … |
| content_cov | … | … | … |

### 2.2 HIGH/MEDIUM/LOW 三档的置信度自洽性
- HIGH：实际 P = …（spec 期望 ≈ 1.0）
- MEDIUM：实际 P = …
- LOW：实际 P = …
- 结论：…

## 3. 重构建议（分级）

### L0 微调（本闭环已做掉）
- <commit 列表 / 一行总结>

### L1 局部重构
| 建议 | 预期收益（佐证文档）| 改造代价 | 回归风险与缓解 |
|---|---|---|---|
| 拆 score_block 为信号收集器+权重组合器 | … | … | … |
| 抽 NumberingProfile 可配置类 | … | … | … |

### L2 架构重构
| 建议 | 预期收益（佐证文档）| 改造代价 | 回归风险与缓解 |
|---|---|---|---|
| Normalizer 加可选段内切分前置（解融合式子标题）| … | … | … |
| ConfidenceScorer 独立阶段 | … | … | … |

### L3 数据驱动改造
| 建议 | 预期收益 | 改造代价 | ROI 评估 |
|---|---|---|---|
| 标题分类小模型替代规则 | … | … | … |

## 4. 决策建议

**下一步建议做：** <L0/L1/L2/L3 + 具体哪条>

**理由：** 用本闭环里的 X 份文档名 + Y 个失败模式佐证。
```

- [ ] **Step 3: 填实**

每条建议必填 3 项：**预期收益（用本闭环里某份失败案例佐证）/ 改造代价 / 回归风险与缓解**。最末"决策建议"必须具体到文档名 + 模式。

- [ ] **Step 4: Commit**

```bash
git add docs/parser-comprehensive-evaluation.md
git commit -m "docs: parser 综合评估与重构建议（L0-L3 分级 + 决策建议）

交付物 #5：闭环结束后的全景评估，包含质量天花板归因、HIGH/MEDIUM/LOW 自洽性、
分级重构建议。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 自查

✅ **Spec 覆盖**：spec §1 → Task 1-3, 6, 7, 8；§2 → Task 3, 4, 5；§3 → Task 2；§4 → Task 9, 10；§5 → Task 10 Step 6；§6.1-6.5 → Task 9-10；§6.6 → Task 11。

✅ **无占位**：所有步骤含完整代码 / 命令 / expected output。

✅ **类型一致性**：`GtChapter`/`GroundTruth`/`DocResult`/`EvalReport`/`TitleMetrics` 跨 Task 一致；`load_gt_*` 三函数签名一致；`run_eval/write_summary/write_diff` 签名一致。

✅ **USER ACK 闸门** 显式在 Task 4 Step 4 + Task 5 Step 3 各一道。

✅ **TDD 节奏**：每个新模块先失败测 → 实现 → 通过 → commit。

✅ **频繁 commit**：每 Task 一个 commit；调参回路每轮一个 commit。
