# P5 前端边界：provenance 标识 + 租户隔离确认（Phase 0 轻量）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在字典管理页可视化规则**来源 provenance**（`manual` 本租户钉死 / `learned` 本租户自动学到——后者本身就是护城河体验化），并确认复查/字典数据已按租户隔离（P2 后 API 自动 per-tenant）。**Phase 0 刻意轻量**：平台运营面（跨租户收敛曲线看板）、scope 维度的完整视角分化**明确推迟到 Phase 1**（spec §6.3、§8）。

**Architecture:** P2 后所有 `heading_rule`/`numbering_profile` 行都带 `company_id`、API 经 ORM 事件自动只返回本租户行——租户隔离在前端**无需额外工作**，只需"可见性已隔离"的验证测试。provenance 是低成本高体验：`source` 字段前端已可得（P1e 的 `HeadingRuleOut` 含 `source`），P5 把它渲染成徽标。yaml 平台默认不是 DB 行（不在列表里），故不在本期做"平台默认只读行"——留 Phase 1。

**Tech Stack:** Vue 3、Element Plus、vitest。

**前置：** P1e（管理页）、P2（租户化 + API 隔离）落地。

---

## File Structure
- `frontend/src/views/settings/HeadingRulesView.vue`（modify：source provenance 徽标）
- `frontend/src/types/parse.ts` 或字典类型处（modify，按需：确认 `source` 在前端类型可得）
- `frontend/tests/unit/HeadingRulesView.spec.ts`（modify：provenance 渲染断言）
- `backend/tests/integration/test_dict_tenant_isolation.py`（modify：补 API 层可见性隔离用例）

---

## Task 1: 管理页 provenance 徽标

**Files:**
- Modify: `frontend/src/views/settings/HeadingRulesView.vue`

- [ ] **Step 1: 确认前端规则类型含 source**

Run: `cd frontend && grep -rn "source" src/api/headingRules.ts`
Expected: `HeadingRule`（或等价）类型含 `source: string`（P1e checkout 带入）。若缺则在该类型加 `source: 'manual' | 'learned'`。

- [ ] **Step 2: 在规则表渲染 source 徽标**

`HeadingRulesView.vue` 的样式规则表（el-table）中，为 `source` 列加 `el-tag`：

```vue
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.source === 'learned'" type="success" size="small" effect="plain"
              title="本组织从你的编辑中自动学到">自动学习</el-tag>
            <el-tag v-else-if="row.source === 'manual'" type="info" size="small" effect="plain"
              title="本组织管理员钉死">手动钉死</el-tag>
            <el-tag v-else size="small" effect="plain">{{ row.source }}</el-tag>
          </template>
        </el-table-column>
```

> 若管理页已有 source 列，仅把纯文本替换为上面的徽标渲染。编号体例表同理（可选，`numbering_profile` 亦有 `source`）。

- [ ] **Step 3: tsc + eslint**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | grep HeadingRulesView || echo "无类型错误"; npx eslint src/views/settings/HeadingRulesView.vue`
Expected: 无错。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/settings/HeadingRulesView.vue
git commit -m "feat(fe): 字典规则 provenance 徽标(自动学习/手动钉死) (P5 Task1)"
```

---

## Task 2: provenance 渲染前端测试

**Files:**
- Modify: `frontend/tests/unit/HeadingRulesView.spec.ts`

- [ ] **Step 1: 追加断言**

mock api 返回含 `source: 'learned'` 与 `source: 'manual'` 两条规则，断言渲染出「自动学习」「手动钉死」徽标文案。

```ts
it('renders provenance badges for learned/manual rules', async () => {
  // mock listHeadingRules → [{...source:'learned'}, {...source:'manual'}]
  // mount HeadingRulesView，await flush
  // expect(wrapper.text()).toContain('自动学习')
  // expect(wrapper.text()).toContain('手动钉死')
})
```

> 具体 mock/挂载沿用 P1e Task6 建立的 HeadingRulesView.spec 风格。

- [ ] **Step 2: 跑**

Run: `cd frontend && npx vitest run tests/unit/HeadingRulesView.spec.ts`
Expected: PASS。

- [ ] **Step 3: 提交**

```bash
git add frontend/tests/unit/HeadingRulesView.spec.ts
git commit -m "test(fe): provenance 徽标渲染断言 (P5 Task2)"
```

---

## Task 3: 字典 API 可见性隔离确认（后端集成）

**Files:**
- Modify: `backend/tests/integration/test_dict_tenant_isolation.py`（追加）

- [ ] **Step 1: 写"租户只通过 API 见到自己规则"用例**

借助 `client` + 设租户上下文（若 TestClient 经 `tenant_middleware` 取 header，则按主线既有租户测试方式注入；否则在 dependency override 里设 company）。断言：A 公司建的规则，B 公司 `GET /api/v1/heading-rules` 看不到。

```python
def test_api_list_isolated_per_tenant(client, db, two_companies):
    # 依主线租户上下文注入方式设当前公司（参考既有 CMMS 租户集成测试写法）
    # A 建规则 → 切 B → GET 列表不含 A 的规则
    ...
```

> 若主线尚无"为请求设 company"的测试范式，复用 `test_dict_tenant_isolation.py` 的 service 级隔离已足够覆盖隔离正确性，此 API 级用例可标 `@pytest.mark.skip(reason="待 DEP-0 请求级租户注入测试范式，Phase 1")` —— 明确记录而非静默省略。

- [ ] **Step 2: 跑**

Run: `cd backend && python -m pytest tests/integration/test_dict_tenant_isolation.py -v`
Expected: PASS（或显式 skip 并注明原因）。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_dict_tenant_isolation.py
git commit -m "test(tenant): 字典 API 可见性隔离确认 (P5 Task3)"
```

---

## Task 4: 全量校验

- [ ] **Step 1: 前端全量**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src --ext .ts,.vue && npx vitest run`
Expected: 全绿。

- [ ] **Step 2: 后端全量**

Run: `cd backend && python -m pytest -q`
Expected: 全 PASS、golden 不变。

---

## Phase 1 明确延后项（本 plan 不做，避免过度设计）
- **scope 维度 + 平台默认只读行**：yaml 平台默认非 DB 行，"平台默认 vs 租户"完整 scope 化需平台默认落库或前端合并展示——Phase 1。
- **平台运营面**：跨租户健康看板、每租户收敛曲线 KPI、冷启动卡点——Phase 1（spec §8）。
- **复查面板 HIGH 绿色细分**"L0 标准样式(全局) vs L1 你公司教会的(租户)"——nice-to-have，Phase 1。

## Self-Review 记录
- **Spec 覆盖**：实现 spec §6.3 的 Phase 0 轻量部分（provenance 标识 + 数据按租户隔离确认）；§8 平台运营面/scope 视角分化明确标注 Phase 1，与 spec "Phase 0 前端基本不动、真正分化在 Phase 1" 一致。
- **占位符**：无 TBD；Task3 的 skip 是**显式记录的延后**（带 reason），非静默省略——符合"no silent caps"。
- **YAGNI**：不在 Phase 0 强行做 scope/平台运营面，避免过度设计。
- **零回归**：纯增量徽标 + 测试；golden 不变。
