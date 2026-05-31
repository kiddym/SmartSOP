# P1e 前端字典界面（管理页 + 记住此样式 + 类型，单租户）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把动态字典的前端移植进主线：标题字典管理页 `HeadingRulesView`（样式规则 + 编号体例 CRUD）+ 编辑器「记住此样式」按钮（M2）+ 归因类型字段。落地后：`/settings/heading-rules` 可视化维护规则/体例；编辑器对样式 review 标题一键钉死。**单租户**。

**Architecture:** 三个**新文件**（`HeadingRulesView.vue`、`api/headingRules.ts`、`api/numberingProfiles.ts`）可 `git checkout` 自 `origin/feat/dynamic-heading-dictionary`（`$SRC`）。其余改动文件（`types/parse.ts`、`types/node.ts`、`router/index.ts`、`AppTopBar.vue`、`NodeDetailPanel.vue`）在主线含 CMMS 改动，且 parser 线 diff **夹带了多个无关变更**（`level_of_use`、品牌名改写、删除节点按钮、sticky 布局）——一律**外科补、按 EXCLUDE 清单剔除**。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Element Plus、Vue Router、vitest。

**前置：** P1b（`/heading-rules` API）、P1d（`/numbering-profiles` API）后端已落地。

### ⚠️ 全局 EXCLUDE 清单（parser 线夹带、**不得移植**）
- `level_of_use` / `LevelOfUse`（`types/parse.ts`、`api/parse.ts`、`ImportRequest`）——无关特性。
- `AppTopBar.vue` 把 `{{ $t('app.name') }}` 改成硬编码 `Smart SOP`——无关品牌改写。
- `NodeDetailPanel.vue` 的「删除此节点」`onRemove`/`node-ops` 块、`isHeading`、sticky review-bar CSS 改写——无关功能。
- `FieldManageView.vue` 的 49 行改动——无关重构。

---

## File Structure
- `frontend/src/api/headingRules.ts`（port，新）
- `frontend/src/api/numberingProfiles.ts`（port，新）
- `frontend/src/views/settings/HeadingRulesView.vue`（port，新）
- `frontend/src/types/parse.ts`（surgical：+2 归因字段于 ParsedNode、+1 于 ImportNode）
- `frontend/src/types/node.ts`（surgical：+source_style_name 于 Node）
- `frontend/src/router/index.ts`（surgical：+heading-rules 路由）
- `frontend/src/components/AppTopBar.vue`（surgical：+菜单项一行）
- `frontend/src/components/editor/NodeDetailPanel.vue`（surgical：+记住此样式）
- `frontend/tests/unit/*`（port/author：api + 管理页 + 按钮）

---

## Task 1: 前端依赖核实（确认接口存在 + 测试基建）

**Files:** 无（只读核实）

- [ ] **Step 1: 核实「记住此样式」依赖的现有接口**

Run:

```bash
cd frontend
grep -rn "confirmReview" src/store/nodeEditor.ts || echo "✗ store.confirmReview 缺失"
grep -rn "errorMessage" src/api/http.ts || echo "✗ api/http.errorMessage 缺失"
grep -rn "createHeadingRule" src/api/  # P1e 将新建 api/headingRules.ts，此处应暂空
```

记录：
- 若 `store.confirmReview` 缺失 → 在 Task 5 用 store 实际的「确认 review」方法名替代（查 `nodeEditor.ts` 中 mark_status 改 unmarked 的 action）。
- 若 `errorMessage` 缺失 → Task 5 改用主线既有的错误提示工具（查其它 view 的 catch 写法）。

- [ ] **Step 2: 核实 vitest 配置与 setup**

Run: `cd frontend && grep -nE "setupFiles|environment|jsdom" vite.config.* vitest.config.* 2>/dev/null; ls tests/`
记录 vitest 用的环境（jsdom）与是否需要 setup 文件。主线无 `tests/setup.ts`——Task 6 移植前端测试时**不引入** parser 线的 setup，沿用主线既有夹具风格（参考 `tests/unit/AppTopBar.spec.ts`）。

- [ ] **Step 3: 记录核实结论**（作为 Task 5/6 适配依据）

---

## Task 2: 新建 API 客户端（checkout）

**Files:**
- Port: `frontend/src/api/headingRules.ts`、`frontend/src/api/numberingProfiles.ts`

- [ ] **Step 1: 取两个 api 文件**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- \
  frontend/src/api/headingRules.ts \
  frontend/src/api/numberingProfiles.ts
```

- [ ] **Step 2: 核实无夹带依赖**

Run: `grep -nE "level_of_use|LevelOfUse" frontend/src/api/headingRules.ts frontend/src/api/numberingProfiles.ts || echo "干净，无 level_of_use"`
Expected: `干净`。并确认它们 import 的 http 客户端路径在主线存在（`grep "from '@/api/http'" frontend/src/api/headingRules.ts` → 对照主线 `src/api/http.ts` 导出）。

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | grep -E "headingRules|numberingProfiles" || echo "无类型错误"`
Expected: `无类型错误`（依赖的 `HeadingRule`/`NumberingProfile` 类型若在 api 文件内联定义则自洽；若引用 `@/types/*` 需 Task 3 先就位——如报缺类型，先做 Task 3 再回此步）。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/headingRules.ts frontend/src/api/numberingProfiles.ts
git commit -m "feat(fe): 字典 API 客户端 headingRules/numberingProfiles (P1e Task2 port)"
```

---

## Task 3: 归因类型字段（surgical）

**Files:**
- Modify: `frontend/src/types/parse.ts`、`frontend/src/types/node.ts`

- [ ] **Step 1: types/parse.ts —— 只加归因字段，排除 level_of_use**

在 `ParsedNode` interface 的 `heading_source` 后加：

```ts
  // 学习闭环归因键（动态标题字典 M1/M2）：样式标题记来源样式名；启发式编号标题记 pattern_key。
  source_style_name: string | null
  source_numbering_pattern: string | null
```

在 `ImportNode` interface 的 `mark_status` 后加：

```ts
  source_style_name?: string | null // 来源样式名（动态字典 M2），随导入持久化
```

> **不要**加 `import type { LevelOfUse }`、**不要**给 `ImportRequest` 加 `level_of_use`（EXCLUDE 清单）。

- [ ] **Step 2: types/node.ts —— Node 加 source_style_name**

在 `Node` interface 的 `mark_status` 后加：

```ts
  source_style_name?: string | null // 来源样式名（动态字典「记住此样式」归因，M2；旧数据可空缺）
```

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | grep -E "types/parse|types/node" || echo "无类型错误"`
Expected: `无类型错误`。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types/parse.ts frontend/src/types/node.ts
git commit -m "feat(fe): ParsedNode/ImportNode/Node 归因类型字段 (P1e Task3)"
```

---

## Task 4: 管理页 + 路由 + 导航（checkout view + surgical route/nav）

**Files:**
- Port: `frontend/src/views/settings/HeadingRulesView.vue`
- Modify: `frontend/src/router/index.ts`、`frontend/src/components/AppTopBar.vue`

- [ ] **Step 1: 取管理页**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- frontend/src/views/settings/HeadingRulesView.vue
```

- [ ] **Step 2: router 加路由（surgical，加在 settings/fields 路由后）**

`frontend/src/router/index.ts` 的 routes 数组中加：

```ts
  {
    path: '/settings/heading-rules',
    name: 'heading-rules',
    component: () => import('@/views/settings/HeadingRulesView.vue'),
    meta: { title: '标题字典' },
  },
```

- [ ] **Step 3: AppTopBar 加菜单项（surgical，只加一行，勿改品牌名）**

`frontend/src/components/AppTopBar.vue` 的 `MENU_COMMANDS` 中「字段管理」一项后加：

```ts
  { group: '配置', label: '标题字典', path: '/settings/heading-rules' },
```

> **不要**改 `<span class="app-brand">{{ $t('app.name') }}</span>`（EXCLUDE 品牌改写）。

- [ ] **Step 4: 类型检查 + 构建可达**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | grep -E "HeadingRulesView|router|AppTopBar" || echo "无类型错误"`
Expected: `无类型错误`（HeadingRulesView 依赖 Task2 的 api + Task3 的类型，均已就位）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/settings/HeadingRulesView.vue frontend/src/router/index.ts frontend/src/components/AppTopBar.vue
git commit -m "feat(fe): 标题字典管理页 + 路由 + 导航入口 (P1e Task4)"
```

---

## Task 5: 编辑器「记住此样式」（surgical，只取 M2 相关）

**Files:**
- Modify: `frontend/src/components/editor/NodeDetailPanel.vue`

- [ ] **Step 1: script 区加 import**

`<script setup>` 顶部 import 区加：

```ts
import { ElMessage } from 'element-plus'         // 若已 import ElMessageBox，合并为 { ElMessage, ElMessageBox }
import { createHeadingRule } from '@/api/headingRules'
import { errorMessage } from '@/api/http'        // 若 Task1 核实缺失，改用主线既有错误提示工具
```

- [ ] **Step 2: 加 computed + rememberStyle（放在 `node`/`procId` computed 附近）**

```ts
const LEVEL_LABEL: Record<number, string> = { 1: '一级章节', 2: '二级章节', 3: '三级章节' }
const sourceStyle = computed(() => node.value?.source_style_name ?? null)
const canRemember = computed(
  () => !!sourceStyle.value && node.value?.heading_level != null && !props.readonly,
)
async function rememberStyle(): Promise<void> {
  const n = node.value
  if (!n || !n.source_style_name || n.heading_level == null) return
  try {
    await createHeadingRule(n.source_style_name, n.heading_level)
    await store.confirmReview(n.id) // 记住即确认（Task1 若方法名不同则替换）
    ElMessage.success(
      `已记住「${n.source_style_name}」为${LEVEL_LABEL[n.heading_level] ?? '章节'}，下次同样式免确认`,
    )
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? '记住样式失败，请重试')
  }
}
```

> **不要**移植 `isHeading`、`onRemove`、`node-ops` 块（EXCLUDE 删除节点功能）。

- [ ] **Step 3: template 在 review-bar 内「确认」按钮后加按钮**

找到现有 review-bar（`v-if="node.mark_status === 'review' && !props.readonly"`）中的「确认」`el-button` 后加：

```vue
      <el-button
        v-if="canRemember"
        class="remember-style"
        size="small"
        title="把此样式→当前层级写入字典，下次同样式自动识别、免确认"
        @click="rememberStyle"
      >记住「{{ sourceStyle }}」样式</el-button>
```

> **不要**改 review-bar 的 CSS 为 sticky、**不要**加 node-ops 区块（EXCLUDE 布局改写）。

- [ ] **Step 4: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | grep -E "NodeDetailPanel" || echo "无类型错误"`
Expected: `无类型错误`。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/NodeDetailPanel.vue
git commit -m "feat(fe): 编辑器「记住此样式」按钮(M2)，仅 review 样式标题可见 (P1e Task5)"
```

---

## Task 6: 前端测试 + 构建校验

**Files:**
- Author: `frontend/tests/unit/headingRulesApi.spec.ts`、`frontend/tests/unit/numberingProfilesApi.spec.ts`、`frontend/tests/unit/HeadingRulesView.spec.ts`、`frontend/tests/unit/NodeDetailPanel.spec.ts`

- [ ] **Step 1: 尝试移植分支对应 spec 作为起点**

```bash
git checkout origin/feat/dynamic-heading-dictionary -- \
  frontend/tests/unit/headingRulesApi.spec.ts \
  frontend/tests/unit/numberingProfilesApi.spec.ts \
  frontend/tests/unit/HeadingRulesView.spec.ts 2>/dev/null || echo "部分 spec 不存在，按下步自写"
```

- [ ] **Step 2: 跑并按主线测试基建适配**

Run: `cd frontend && npx vitest run tests/unit/headingRulesApi.spec.ts tests/unit/numberingProfilesApi.spec.ts tests/unit/HeadingRulesView.spec.ts`
Expected: PASS。若因 parser 线 `tests/setup.ts`/夹具差异失败 → 参照主线 `tests/unit/AppTopBar.spec.ts` 的 mock/挂载风格改写（**不引入** parser 线 setup.ts）。最低限度保证：
- `headingRulesApi.spec`：mock http，断言 `createHeadingRule`/`listHeadingRules` 发对 URL/body。
- `HeadingRulesView.spec`：mock api，断言加载列表、新增、启停渲染。

- [ ] **Step 3: NodeDetailPanel「记住此样式」按钮测试**

`frontend/tests/unit/NodeDetailPanel.spec.ts`（新增或追加）——断言：样式来源 review 标题显示「记住」按钮、点击调用 `createHeadingRule(source_style_name, heading_level)`；无 `source_style_name` 时按钮不渲染。mock `@/api/headingRules` 与 store。

Run: `cd frontend && npx vitest run tests/unit/NodeDetailPanel.spec.ts`
Expected: PASS。

- [ ] **Step 4: 全量前端校验**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src --ext .ts,.vue && npx vitest run`
Expected: tsc 0 错、eslint 0 错、vitest 全 PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/tests/
git commit -m "test(fe): 字典 api/管理页/记住样式 前端测试 (P1e Task6)"
```

---

## Self-Review 记录

- **Spec 覆盖**：实现 spec §6.3 前端的单租户基础形态（管理页 + 记住此样式 + 类型）。scope/provenance 维度与平台运营面是 **P5**（依赖 P2 租户化）——P1e 不做，避免过度设计。
- **占位符**：无 TBD。Task1 的依赖核实 + Task5/6 的"方法名/测试基建按主线适配"是**明确的条件处置指引**（含命令与 fallback），非占位符。
- **EXCLUDE 严格**：全局 EXCLUDE 清单 + 每个 surgical Task 内重申不移植项（level_of_use/品牌名/删除节点/sticky/FieldManageView）——防止把 parser 线无关变更带进主线。
- **依赖顺序**：Task2(api)→Task3(types)→Task4(view 依赖前两者)→Task5(按钮依赖 api)→Task6(测试)。
- **类型一致**：`createHeadingRule(styleName, level)` 在 NodeDetailPanel 调用与 `api/headingRules.ts` 定义一致（Task2 checkout 后若签名不同，按其实际签名调整 Task5 调用）。
