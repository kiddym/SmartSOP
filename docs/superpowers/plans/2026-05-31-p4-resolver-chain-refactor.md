# P4 内部重构 ResolverChain + NumberingProfile 收口（零行为变化）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `styles.classify_with_source` 的多级反查重构为显式 `ResolverChain`，把散落的编号正则 `_RE_*` 收进 `NumberingProfile` 对象。**纯内部结构化、对外 API 不变、逐字节零行为变化**——为 Phase 2「中心化分类器替换 HeuristicResolver 一个插槽」铺路。

**Architecture:** 这是**重构**（非移植、非新功能）。唯一正确性判据是 **golden 回归 + 66 个 parser 单测逐字节不变**。每步小幅提取 + 立即跑全套 parser 测试，任何漂移即回退。不改任何调用方签名（`classify_with_source` / `classify_numbering` 对外形态保持）。

**Tech Stack:** Python、pytest、P0 golden（`tests/regression`）。

**前置：** P1a（parser 已含 P1/overrides）。P4 不依赖 P2/P3，可与 P1+ 并行。

---

## File Structure
- `backend/app/parser/resolvers.py`（新）：`Resolver` 协议 + `StyleResolver`/`SynonymResolver`/`OutlineResolver`/`BasedOnResolver` + `ResolverChain`
- `backend/app/parser/styles.py`（modify）：`classify_with_source` 内部改用 `ResolverChain`，签名不变
- `backend/app/parser/numbering_profile_rules.py`（新）：`NumberingProfile` 收编 `_RE_*` + `load_default_profile()`
- `backend/app/parser/heading_detector.py`（modify）：`_classify_numbering_base` 内部改用 `NumberingProfile`，签名不变
- `backend/tests/unit/parser/test_resolver_chain.py`（author）

---

## Task 1: 抽取 ResolverChain（行为等价）

**Files:**
- Create: `backend/app/parser/resolvers.py`
- Modify: `backend/app/parser/styles.py`

- [ ] **Step 1: 跑基线，记录当前 parser 全绿**

Run: `cd backend && python -m pytest tests/unit/parser tests/regression -q`
Expected: 全 PASS（这是重构前的"绿基线"）。

- [ ] **Step 2: 新建 resolvers.py，封装现有四级逻辑**

把 `classify_with_source` 现有的判定顺序（override → 标准名 → synonym → outlineLvl → basedOn）拆成独立 resolver，每个返回 `(level, source) | None`：

```python
"""标题层级反查责任链（P4 重构，行为等价于原 classify_with_source）。

每个 Resolver 接收 (style_info, ctx) 返回 (level, source) 或 None（不命中→下一个）。
Phase 2 的中心化分类器将作为新 Resolver 替换 HeuristicResolver 插槽，不动其余。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# ctx 至少含：name(样式显示名)、synonyms、style_overrides、standard 名查找、basedOn 递归回调。
# 具体字段以从 styles.classify_with_source 平移的现有逻辑为准（不新增信号）。


@dataclass
class ResolverChain:
    resolvers: list[Callable[..., tuple[int, str] | None]]

    def resolve(self, *args, **kwargs) -> tuple[int | None, str | None]:
        for r in self.resolvers:
            hit = r(*args, **kwargs)
            if hit is not None:
                return hit
        return None, None
```

> 把 styles.py 中 `# 1.~5.` 五段判定逐段平移为 resolver 函数/可调用对象，**逻辑一字不改**，仅换组织形式。basedOn 递归仍调用 `classify_with_source`（保持等价）。

- [ ] **Step 3: classify_with_source 改用链，签名不变**

`classify_with_source(style_id, index, *, synonyms=None, style_overrides=None)` 对外签名、返回 `(level, source)` 形态、来源枚举 `{override,style,synonym,outline,based_on}` **全部不变**，内部组装 `ResolverChain([...]).resolve(...)`。

- [ ] **Step 4: 跑全套 parser + golden，必须逐字节不变**

Run: `cd backend && python -m pytest tests/unit/parser tests/regression -v`
Expected: 全 PASS，**golden 零漂移**。任何失败 → 说明平移引入了行为差异，回退重做该 resolver。

- [ ] **Step 5: 提交**

```bash
git add backend/app/parser/resolvers.py backend/app/parser/styles.py
git commit -m "refactor(parser): classify_with_source → ResolverChain(行为等价) (P4 Task1)"
```

---

## Task 2: ResolverChain 单测（锁定插槽契约）

**Files:**
- Create: `backend/tests/unit/parser/test_resolver_chain.py`

- [ ] **Step 1: 写链路单测**

```python
"""ResolverChain 行为契约（P4）。"""
from __future__ import annotations

from app.parser.resolvers import ResolverChain


def test_first_hit_wins() -> None:
    chain = ResolverChain([lambda: (2, "override"), lambda: (1, "synonym")])
    assert chain.resolve() == (2, "override")


def test_all_miss_returns_none_pair() -> None:
    chain = ResolverChain([lambda: None, lambda: None])
    assert chain.resolve() == (None, None)


def test_later_resolver_used_when_earlier_misses() -> None:
    chain = ResolverChain([lambda: None, lambda: (3, "based_on")])
    assert chain.resolve() == (3, "based_on")
```

- [ ] **Step 2: 跑**

Run: `cd backend && python -m pytest tests/unit/parser/test_resolver_chain.py -v`
Expected: 全 PASS。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/unit/parser/test_resolver_chain.py
git commit -m "test(parser): ResolverChain 契约单测 (P4 Task2)"
```

---

## Task 3: NumberingProfile 收口 _RE_*（行为等价）

**Files:**
- Create: `backend/app/parser/numbering_profile_rules.py`
- Modify: `backend/app/parser/heading_detector.py`

- [ ] **Step 1: 把散落 _RE_* 收进 NumberingProfile**

`numbering_profile_rules.py`：把 `heading_detector.py` 里的编号正则集中为一个 profile 对象，`load_default_profile()` 返回内置体例；`_classify_numbering_base` 改为从 profile 取规则。**正则与判定逻辑一字不改**，仅集中存放。预留 `load_profile_for(company_id)` 入口（暂返回默认，租户编号体例已由 P1d 的 `numbering_overrides` 注入承载，此处仅为结构留缝）。

- [ ] **Step 2: heading_detector 内部改用 profile，签名不变**

`classify_numbering(text, overrides=None)` 对外签名、`overrides` 空时与内置逐字节一致的契约（P1a 已固化）**不变**。

- [ ] **Step 3: 跑全套 parser + golden，逐字节不变**

Run: `cd backend && python -m pytest tests/unit/parser tests/regression -v`
Expected: 全 PASS、golden 零漂移；尤其 P1a 的 `test_dotted_dunhao_subsection_is_heading` 等编号用例不变。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/numbering_profile_rules.py backend/app/parser/heading_detector.py
git commit -m "refactor(parser): _RE_* 收口进 NumberingProfile(行为等价) (P4 Task3)"
```

---

## Task 4: 全量回归 + lint

- [ ] **Step 1: 全 parser + regression**

Run: `cd backend && python -m pytest tests/unit/parser tests/regression -v`
Expected: 全 PASS、golden 不变。

- [ ] **Step 2: ruff**

Run: `cd backend && ruff check app/parser/resolvers.py app/parser/numbering_profile_rules.py app/parser/styles.py app/parser/heading_detector.py tests/unit/parser/test_resolver_chain.py`
Expected: 无 error。

- [ ] **Step 3: 提交（如有修正）**

```bash
git add -A && git commit -m "chore(parser): ruff 修正 (P4 Task4)" || echo "无需提交"
```

---

## Self-Review 记录
- **Spec 覆盖**：实现 spec §6.1（ResolverChain）+ §6.2（NumberingProfile 收口）；为 §7.2 Phase 2 分类器插槽铺路。
- **占位符**：无 TBD；"逐段平移、逻辑一字不改"是重构的明确约束，正确性由 golden + 66 parser 单测的逐字节判据保证（非占位符——验证手段具体且可执行）。
- **零行为变化是硬契约**：每个提取 Task 后立即跑 golden + 全 parser 测试，漂移即回退。对外 API（`classify_with_source`/`classify_numbering` 签名与返回形态）不变。
- **独立性**：不依赖 P2/P3，可并行。
