# P1a parser P1 修复 + 归因下穿（移植）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `feat/dynamic-heading-dictionary` 上的 **parser 层增量**（P1 跨 numId 层级修复 `_assign_styled_depths`、整句正文 prose 检测、`source_style_name`/`source_numbering_pattern` 归因下穿、`numbering_overrides` 形参管线）移植进主线 `phase-0-platform-foundation`，使主线解析达到 parser 线水平：TP试验程序解析为 `{1:29, 2:11, 3:3}`，且 `/parse` 响应携带归因字段。**不含任何 DB / service / 字典**——`numbering_overrides` 形参喂 `None`，留待 P1d 接线。

**Architecture:** 这是一次**移植（port）**，不是从零开发——目标代码已在 parser 分支且已带单测。涉及 8 个纯函数 parser 文件 + 3 个 parser 单测文件，均无租户 mixin、可整文件 `git checkout` 自分支取得（分支为主线 parser 的超集：P0 两边皆有，分支多 P1）。移植后以 P0 的 golden 回归脚本 + 移植带来的单测验证，并**故意更新** golden 中 TP 等受 P1 影响的条目。

**Tech Stack:** Python 3.11+、`app.parser`（normalizer→structurer→serializer 三阶段）、pytest、P0 的 `app.parser.eval.accuracy`。

---

## File Structure

移植来源分支：`origin/feat/dynamic-heading-dictionary`（下称 `$SRC`）。

**实现文件（自 `$SRC` 整文件取，纯解析、无租户）：**
- `backend/app/parser/ir.py`（+`num_id`/`num_ilvl` 字段）
- `backend/app/parser/normalizer.py`（采集段落 `numPr` 的 numId/ilvl）
- `backend/app/parser/heading_detector.py`（`classify_numbering(text, overrides=None)` 壳 + `_classify_numbering_base` + `DocStats.numbering_overrides`；主线已有 P0 顿号修复，分支为其超集）
- `backend/app/parser/structurer.py`（P1 `_assign_styled_depths`/`_refine_styled_level` + `_looks_like_prose` + `_attribution` + `numbering_overrides` 穿线）
- `backend/app/parser/result.py`（`ParsedNode.{source_style_name, source_numbering_pattern}`）
- `backend/app/parser/__init__.py`（`parse_docx(..., numbering_overrides=None)`）
- `backend/app/parser/validators/completeness.py`（**reconcile 点**：主线与分支可能不同口径，见 Task 7）
- `backend/app/schemas/parse.py`（`ParsedNodeOut` 同名两归因字段）

**测试文件（自 `$SRC` 整文件取）：**
- `backend/tests/unit/parser/test_structurer.py`（+82：`_assign_styled_depths` ×3、prose、归因）
- `backend/tests/unit/parser/test_heading_detector.py`（+24：overrides 壳）

**golden 更新：**
- `backend/tests/regression/parser_baseline.json`（P0 产出；本 plan 故意更新受 P1 影响条目）

> 前置：P0 plan 已落地（`app.parser.eval.accuracy` + golden 存在）。

---

## Task 1: 移植前差异核对（确认分支是主线 parser 超集，无主线独有改动会丢）

**Files:** 无（只读核对）

- [ ] **Step 1: 逐文件 diff，确认没有"主线有、分支无"的 parser 改动**

Run:

```bash
SRC=origin/feat/dynamic-heading-dictionary
for f in backend/app/parser/ir.py backend/app/parser/normalizer.py \
         backend/app/parser/heading_detector.py backend/app/parser/structurer.py \
         backend/app/parser/result.py backend/app/parser/__init__.py \
         backend/app/parser/validators/completeness.py backend/app/schemas/parse.py; do
  echo "=== $f ==="
  # 主线相对分支独有的删除行（分支缺的主线内容）——理想为空
  git diff "$SRC...phase-0-platform-foundation" -- "$f" | grep '^-' | grep -v '^---' || echo "(分支已含主线全部内容)"
done
```

Expected: 每个文件输出 `(分支已含主线全部内容)` 或仅注释/格式行差异。
**若 `heading_detector.py` 或 `completeness.py` 出现主线独有逻辑行** → 记录下来，Task 3/7 改为"手工合并"而非整文件覆盖。

- [ ] **Step 2: 记录核对结论**

把 Step 1 中任何非空输出（主线独有行）记入本 Task 的复核备注，作为后续 reconcile 依据。无独有行则记"全部可整文件移植"。

---

## Task 2: 移植 ir.py + normalizer.py（Block 增 numId/ilvl 并采集）

**Files:**
- Modify(port): `backend/app/parser/ir.py`、`backend/app/parser/normalizer.py`
- Test: 既有 `backend/tests/unit/parser/test_normalizer*.py`

- [ ] **Step 1: 自分支取这两个文件**

Run:

```bash
SRC=origin/feat/dynamic-heading-dictionary
git checkout "$SRC" -- backend/app/parser/ir.py backend/app/parser/normalizer.py
```

- [ ] **Step 2: 确认 Block 新增字段已在**

Run: `grep -nE "num_id|num_ilvl" backend/app/parser/ir.py`
Expected: 出现 `num_id: str | None` 与 `num_ilvl: int | None`（默认 None）。

- [ ] **Step 3: 跑 normalizer 单测**

Run: `cd backend && python -m pytest tests/unit/parser -k "normaliz or ir" -v`
Expected: PASS（新字段默认 None 向下兼容，既有用例不受影响）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/ir.py backend/app/parser/normalizer.py
git commit -m "feat(parser): Block 采集 numPr numId/ilvl (P1a Task2 port)"
```

---

## Task 3: 移植 heading_detector.py（numbering_overrides 壳，保留主线 P0）

**Files:**
- Modify(port): `backend/app/parser/heading_detector.py`
- Test: `backend/tests/unit/parser/test_heading_detector.py`（Task 8 一并跑）

- [ ] **Step 1: 取文件（若 Task1 标记有主线独有行，改手工合并）**

默认整文件移植（Task1 确认分支为超集时）：

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/app/parser/heading_detector.py
```

- [ ] **Step 2: 确认 P0 顿号修复仍在 + overrides 壳已加**

Run: `grep -nE "depth >= 2|def classify_numbering|_classify_numbering_base|numbering_overrides" backend/app/parser/heading_detector.py`
Expected: 同时出现 `depth >= 2`（P0 未丢）、`def classify_numbering(...overrides...)`、`_classify_numbering_base`、`DocStats` 的 `numbering_overrides`。

- [ ] **Step 3: 跑 heading_detector 单测**

Run: `cd backend && python -m pytest tests/unit/parser/test_heading_detector.py -v`
Expected: 此时可能因 `structurer` 未更新而有 import/调用不一致——若报错与 structurer 相关，**先跳过**，待 Task 4 后统一跑（在 Task 8）。仅确认本文件可 import：`cd backend && python -c "import app.parser.heading_detector"` → 无错。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/heading_detector.py
git commit -m "feat(parser): classify_numbering overrides 壳 + DocStats.numbering_overrides (P1a Task3 port)"
```

---

## Task 4: 移植 structurer.py（P1 修复 + prose + 归因）

**Files:**
- Modify(port): `backend/app/parser/structurer.py`
- Test: `backend/tests/unit/parser/test_structurer.py`（Task 8 跑）

移植核心（参考——以下为分支实际新增，整文件 checkout 即带入）：

```python
def _assign_styled_depths(body_blocks, num_floor):
    """扁平样式文档：按文档顺序把非主大纲 numId 的次要子列表嵌套到当前 section 下，
    修正 per-numId 归一把子列表抬回 L1 的错误（TP numId=11 清单应在 L2 文件准备下→L3）。
    仅扁平样式启用；规范分级文档走基线零回归。"""
    # ... flat 判定 + dominant numId + 顺序栈：depth<=prev 且 prev>=2 → prev+1

def _refine_styled_level(block, base_level, num_floor):
    """max(基线, 段落级深度)：outlineLvl 优先，否则 numPr ilvl 按 num_floor 归一。只加深不变浅。"""

def _looks_like_prose(title):
    """异常长(>=40) 或 较长(>=25)+含句读 → 疑似整句误套样式 → 标 review（不改层级）。"""

def _attribution(block, style_index, stats):
    """样式标题→样式显示名；编号标题→pattern_key。学习归因键。"""
```

- [ ] **Step 1: 取文件**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/app/parser/structurer.py
```

- [ ] **Step 2: 确认关键符号到位**

Run: `grep -nE "_assign_styled_depths|_refine_styled_level|_looks_like_prose|_attribution|numbering_overrides" backend/app/parser/structurer.py`
Expected: 四个函数 + `numbering_overrides` 形参均出现。

- [ ] **Step 3: 确认 import 通**

Run: `cd backend && python -c "import app.parser.structurer; import app.parser"`
Expected: 无 ImportError（依赖 Task2/3 的 ir/heading_detector 已就位）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/structurer.py
git commit -m "feat(parser): P1 跨numId层级修复 + prose检测 + 归因 (P1a Task4 port)"
```

---

## Task 5: 移植 result.py + schemas/parse.py（归因字段）

**Files:**
- Modify(port): `backend/app/parser/result.py`、`backend/app/schemas/parse.py`

- [ ] **Step 1: 取文件**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/app/parser/result.py backend/app/schemas/parse.py
```

- [ ] **Step 2: 确认归因字段**

Run: `grep -nE "source_style_name|source_numbering_pattern" backend/app/parser/result.py backend/app/schemas/parse.py`
Expected: `ParsedNode` 与 `ParsedNodeOut` 各含两字段（默认 None）。

- [ ] **Step 3: import 校验**

Run: `cd backend && python -c "from app.parser.result import ParsedNode; ParsedNode(level=1)"`
Expected: 无错（新字段有默认值）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/result.py backend/app/schemas/parse.py
git commit -m "feat(parser): ParsedNode/Out 归因字段下穿 (P1a Task5 port)"
```

---

## Task 6: 移植 parser/__init__.py（parse_docx 加 numbering_overrides，喂 None）

**Files:**
- Modify(port): `backend/app/parser/__init__.py`

- [ ] **Step 1: 取文件**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- backend/app/parser/__init__.py
```

- [ ] **Step 2: 确认签名**

Run: `grep -nE "def parse_docx|numbering_overrides" backend/app/parser/__init__.py`
Expected: `parse_docx(data, mode="smart", *, style_overrides=None, numbering_overrides=None)`，且向 `structure(...)` 透传 `numbering_overrides`。

- [ ] **Step 3: 端到端 import + 空跑**

Run: `cd backend && python -c "from app.parser import parse_docx; print('ok')"`
Expected: 打印 `ok`。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/__init__.py
git commit -m "feat(parser): parse_docx 增 numbering_overrides 形参(喂None) (P1a Task6 port)"
```

---

## Task 7: Reconcile completeness.py

**Files:**
- Modify: `backend/app/parser/validators/completeness.py`
- Test: `backend/tests/unit/parser` 完整性相关用例

- [ ] **Step 1: 先看主线 vs 分支差异**

Run: `git diff phase-0-platform-foundation..origin/feat/dynamic-heading-dictionary -- backend/app/parser/validators/completeness.py`
Expected: 看清两边口径差异（C003 误报修复相关）。

- [ ] **Step 2: 决策并应用**

- 若 Task1 核对显示**主线无独有逻辑** → 整文件取分支版：
  `git checkout origin/feat/dynamic-heading-dictionary -- backend/app/parser/validators/completeness.py`
- 若主线有独有逻辑（如主线已自行修过 C003）→ **手工合并**：保留主线分母口径，仅补分支新增（不要回退主线）。以两边都"36 份样本无 completeness warning"为正确性判据。

- [ ] **Step 3: 验证无 completeness 误报**

Run: `cd backend && python -c "
from pathlib import Path
from app.parser import parse_docx
from app.parser.eval.accuracy import SAMPLE_ROOT
bad=[]
for p in SAMPLE_ROOT.rglob('*.docx'):
    try:
        r=parse_docx(p.read_bytes(),'smart')
        if any(w.stage=='completeness' for w in r.warnings): bad.append(p.name)
    except Exception: pass
print('completeness 误报文档:', bad)
"`
Expected: `completeness 误报文档: []`（空）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/validators/completeness.py
git commit -m "fix(parser): reconcile completeness 口径，36份无误报 (P1a Task7)"
```

---

## Task 8: 移植 parser 单测并跑全量 parser 套件

**Files:**
- Modify(port): `backend/tests/unit/parser/test_structurer.py`、`backend/tests/unit/parser/test_heading_detector.py`

- [ ] **Step 1: 取分支单测**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- \
  backend/tests/unit/parser/test_structurer.py \
  backend/tests/unit/parser/test_heading_detector.py
```

- [ ] **Step 2: 跑全量 parser 单测**

Run: `cd backend && python -m pytest tests/unit/parser -v`
Expected: 全 PASS（含分支新增的 `_assign_styled_depths` ×3、prose、归因、overrides 壳用例）。
若个别用例依赖 P1d 的 DB（不应有，P1a 纯 parser）——检查是否误取了 service 相关测试；只取上述两文件。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/unit/parser/test_structurer.py backend/tests/unit/parser/test_heading_detector.py
git commit -m "test(parser): 移植 P1/归因/overrides 单测 (P1a Task8 port)"
```

---

## Task 9: 验证 TP 基线 + 故意更新 golden

**Files:**
- Modify: `backend/tests/regression/parser_baseline.json`

- [ ] **Step 1: 实测 TP 分布达标**

Run: `cd backend && python -c "
from app.parser import parse_docx
from app.parser.eval.accuracy import SAMPLE_ROOT, level_distribution
data=(SAMPLE_ROOT/'TP试验程序.docx').read_bytes()
print('TP smart =', level_distribution(parse_docx(data,'smart').chapters))
"`
Expected: `TP smart = {1: 29, 2: 11, 3: 3}`（P1 移植成功的硬判据）。
若不符（如仍 `{1:32,2:11}`）→ 回查 Task2/4 是否完整移植（`num_id`/ilvl 采集 + `_assign_styled_depths`）。

- [ ] **Step 2: 跑现有 golden 回归，预期 FAIL（受 P1 影响条目漂移）**

Run: `cd backend && python -m pytest tests/regression/test_parser_accuracy_baseline.py -v`
Expected: FAIL，差异集中在 TP 及顿号子节文档（12/17/18/22 号等）——这是**有意改动**，非回归。

- [ ] **Step 3: 重生成 golden（P0 Task4 命令）**

Run:

```bash
cd backend && python -c "
import json, pathlib
from app.parser.eval.accuracy import evaluate_corpus
golden={'smart':evaluate_corpus(mode='smart'),'standard':evaluate_corpus(mode='standard')}
p=pathlib.Path('tests/regression/parser_baseline.json')
p.write_text(json.dumps(golden,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
print('regenerated')
"
```

- [ ] **Step 4: 人工核对 golden diff 只含预期文档**

Run: `git diff --stat backend/tests/regression/parser_baseline.json && git diff backend/tests/regression/parser_baseline.json | grep -E '试验程序|"distribution"' | head -30`
Expected: 变化集中在 TP（→`{1:29,2:11,3:3}`）+ 顿号子节文档恢复 2–3 级；**标准样式 4 份不得变化**（零回归红线）。若标准 4 份有变 → 移植引入了回归，回查。

- [ ] **Step 5: 回归测试转绿 + 提交（commit 说明有意更新）**

Run: `cd backend && python -m pytest tests/regression -v`
Expected: PASS。

```bash
git add backend/tests/regression/parser_baseline.json
git commit -m "test(regression): 更新 golden 反映 P1 修复(TP→{1:29,2:11,3:3}+顿号子节恢复)，标准4份零变化 (P1a Task9)"
```

---

## Task 10: 全量回归 + lint

**Files:** 无

- [ ] **Step 1: parser + regression 全跑**

Run: `cd backend && python -m pytest tests/unit/parser tests/regression -v`
Expected: 全 PASS。

- [ ] **Step 2: 后端其余受影响测试（parse_service 等）**

Run: `cd backend && python -m pytest tests/unit/services/test_parse_service.py tests/unit/parser/test_pipeline.py -v`
Expected: PASS。若 `test_parse_service` 因 `numbering_overrides`/归因签名变化而失败 → 该测试的更新属 **P1d/P1b 范围**（DB 注入），P1a 仅保证 parser 纯函数与 pipeline 通过；记录为后续 plan 衔接点，勿在 P1a 改 service。

- [ ] **Step 3: ruff**

Run: `cd backend && ruff check app/parser app/schemas/parse.py tests/unit/parser tests/regression`
Expected: 无 error。

- [ ] **Step 4: 提交（如有 lint 修正）**

```bash
git add -A && git commit -m "chore(parser): ruff 修正 (P1a Task10)" || echo "无需提交"
```

---

## Self-Review 记录

- **Spec 覆盖**：实现 spec §1-B（parser 修复对齐）、§2.2 表中"主线缺 P1/归因"两行、§3.1 的 TP `{1:29,2:11,3:3}` 判据。字典/service/前端由 P1b–P1e 覆盖。
- **占位符**：无 TBD。Task1/3/7 的"若主线有独有行则手工合并"是**条件分支的明确处置指引**（含判据与命令），非占位符；Task4 嵌入了 P1 核心函数的语义说明，完整代码经整文件 `git checkout` 带入（移植场景下转写反增错位风险）。
- **类型一致**：`numbering_overrides: dict[str, tuple[str, int|None]] | None` 在 `__init__`/`structure`/`compute_doc_stats`/`classify_numbering` 间一致；归因字段名 `source_style_name`/`source_numbering_pattern` 在 result/schema/structurer 一致。
- **诚实边界**：P1a 不碰 service/DB；`numbering_overrides` 形参喂 None；`test_parse_service` 若因签名变化失败，明确归属 P1b/P1d，不在此越界修改。
- **零回归红线**：Task9 Step4 显式要求"标准样式 4 份 golden 不变"，否则判定移植引入回归。
