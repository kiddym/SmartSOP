# P3 同义词分层（平台默认 yaml + 每租户覆盖，复用 heading_rule）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把内置 `heading_synonyms.yaml` 明确定位为**平台默认底座**，每租户覆盖**复用 `tb_heading_style_rule`**（P1b/P2 已就位），解析时按"租户规则 > 平台默认同义词"合并。**验证**同一样式名在不同租户解析出不同 level、且无租户规则时回退平台默认。

**Architecture:** 优先级在 `styles.classify_with_source` 中**已实现**：`style_overrides(override) > 标准名 > synonyms(yaml) > outlineLvl > basedOn`。P2 后 `active_style_overrides` 已是 per-tenant，故"租户优先"天然成立——P3 主要是**对抗性验证 + 明确文档定位**，不引入新表（避免与 heading_rule 职责重叠）。仅当验证发现 yaml 被误当成可写/被租户改动污染时才补隔离。

**Tech Stack:** Python、pytest、`app.parser.styles` / `synonyms`。

**前置：** P2 落地（`active_style_overrides` per-tenant）。

---

## File Structure
- `backend/app/parser/data/heading_synonyms.yaml`（modify：仅注释，标注"平台默认底座，租户覆盖走 tb_heading_style_rule"）
- `backend/app/parser/synonyms.py`（modify：docstring 明确"平台默认、全局只读、不随租户变"）
- `backend/tests/integration/test_synonym_layering.py`（author：分层验证）

---

## Task 1: 文档化平台默认定位（仅注释/docstring，零行为变化）

**Files:**
- Modify: `backend/app/parser/data/heading_synonyms.yaml`、`backend/app/parser/synonyms.py`

- [ ] **Step 1: yaml 顶部加定位注释**

`heading_synonyms.yaml` 文件头加：

```yaml
# 平台默认同义词底座（全局只读，随代码发布，不随租户变）。
# 租户级覆盖走 tb_heading_style_rule（manual/learned，按 company_id 隔离）；
# 解析优先级：租户规则(override) > 本文件(synonym) > outlineLvl > basedOn。
```

- [ ] **Step 2: synonyms.py docstring 同步**

`load_default_synonyms` 的 docstring 补一句：「平台默认底座；租户特异同义词不进本文件，走动态字典 tb_heading_style_rule（P1b/P2）」。

- [ ] **Step 3: 解析行为零变化确认**

Run: `cd backend && python -m pytest tests/unit/parser tests/regression -q`
Expected: 全 PASS、golden 不变（纯注释改动）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/parser/data/heading_synonyms.yaml backend/app/parser/synonyms.py
git commit -m "docs(parser): 标注 heading_synonyms.yaml 为平台默认底座 (P3 Task1)"
```

---

## Task 2: 分层验证（租户覆盖 > 平台默认 > 回退默认）

**Files:**
- Create: `backend/tests/integration/test_synonym_layering.py`

- [ ] **Step 1: 选一个 yaml 平台默认里已有的样式名**

Run: `cd backend && python -c "from app.parser.synonyms import load_default_synonyms as L; d=L(); print(list(d.items())[:5])"`
记下一个内置样式名与其默认 level（下文记为 `STYLE` / `DEFAULT_LV`，测试里用实际值替换）。

- [ ] **Step 2: 写分层测试**

`backend/tests/integration/test_synonym_layering.py`：

```python
"""同义词分层：租户规则 > 平台默认 yaml > 回退默认（P3）。"""
from __future__ import annotations

import pytest

from app import tenant
from app.models.company import Company
from app.parser.styles import StyleIndex, StyleInfo, classify_with_source
from app.parser.synonyms import load_default_synonyms
from app.schemas.heading_rule import HeadingRuleCreate
from app.services import heading_rule_service as svc


@pytest.fixture
def company(db):
    c = Company(name="租户X"); db.add(c); db.flush()
    return c.id


def _index_with(style_name: str) -> StyleIndex:
    idx = StyleIndex()
    idx.by_id["sid"] = StyleInfo(style_id="sid", name=style_name, outline_lvl=None, based_on=None)
    return idx


def test_platform_default_applies_without_tenant_rule() -> None:
    syn = load_default_synonyms()
    style, default_lv = next(iter(syn.items()))
    idx = _index_with(style)
    level, source = classify_with_source("sid", idx, synonyms=syn, style_overrides={})
    assert level == default_lv and source == "synonym"  # 回退平台默认


def test_tenant_rule_overrides_platform_default(db, company) -> None:
    syn = load_default_synonyms()
    style, default_lv = next(iter(syn.items()))
    target = 1 if default_lv != 1 else 2  # 选一个与默认不同的层级
    tenant.set_current_company_id(company)
    svc.create(db, HeadingRuleCreate(style_name=style, level=target)); db.flush()
    overrides = svc.active_style_overrides(db)  # per-tenant
    idx = _index_with(style)
    level, source = classify_with_source("sid", idx, synonyms=syn, style_overrides=overrides)
    assert level == target and source == "override"  # 租户规则优先于 yaml
```

> `StyleInfo` 构造字段以 `styles.py` 实际定义为准（若字段名不同按文件调整）。

- [ ] **Step 3: 跑**

Run: `cd backend && python -m pytest tests/integration/test_synonym_layering.py -v`
Expected: 全 PASS（证明租户优先 + 无规则回退平台默认）。

- [ ] **Step 4: 提交**

```bash
git add backend/tests/integration/test_synonym_layering.py
git commit -m "test(tenant): 同义词分层 租户覆盖>平台默认>回退 验证 (P3 Task2)"
```

---

## Self-Review 记录
- **Spec 覆盖**：实现 spec §4.3（E 同义词分层，复用 heading_rule 不新建表）+ §4.2 优先级链验证。
- **占位符**：无 TBD；`STYLE`/`STYLE_INFO 字段` 两处为"按实际数据/定义取值"的明确指引（含查看命令）。
- **YAGNI**：未新建 `tb_tenant_synonym`——分层已由既有优先级 + per-tenant heading_rule 满足，避免重复造表（spec 方案 A）。
- **零行为变化**：Task1 纯注释；golden 不变。
