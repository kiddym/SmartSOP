# 配置中心:部署导向 Hub + 模块聚合页 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「管理」配置从按机制横切重构为部署导向的「配置中心 Hub + 模块聚合页」纵切结构,复用现有页面组件作为 tab,不动后端。

**Architecture:** 新增一个总览 Hub(`/admin/config`)按部署阶段编排入口;4 个聚合页(SOP/工单/请求/统一自定义字段)用 `el-tabs` 把现有 view 组件嵌成 tab;`CustomFieldsView` 加 `lockedEntity`/`embedded` 入参以单实体复用;三个分类 Dialog 抽出无壳 Panel 供 tab 与 Dialog 双用;旧路由全部保留 redirect。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript、Element Plus、vue-router、Pinia、Vitest + @vue/test-utils。

参考 spec:`docs/superpowers/specs/2026-06-08-config-center-deployment-hub-design.md`

---

## 文件结构

**新建:**
- `frontend/src/views/admin/config/ConfigConsoleView.vue` — Hub 总览页(六阶段区块)
- `frontend/src/views/admin/config/SopConfigView.vue` — SOP 配置聚合页
- `frontend/src/views/admin/config/WorkOrderConfigView.vue` — 工单配置聚合页
- `frontend/src/views/admin/config/RequestConfigView.vue` — 请求配置聚合页
- `frontend/src/views/admin/config/CustomFieldsConfigView.vue` — 统一自定义字段聚合页(资产/位置/备件)
- `frontend/src/components/maintenance/WorkOrderCategoryManagePanel.vue` — 工单分类无壳面板
- `frontend/src/components/workorder/TimeCategoryManagePanel.vue` — 工时分类无壳面板
- `frontend/src/components/workorder/CostCategoryManagePanel.vue` — 成本分类无壳面板

**修改:**
- `frontend/src/views/settings/CustomFieldsView.vue` — 加 `lockedEntity`/`embedded` props
- `frontend/src/components/maintenance/WorkOrderCategoryManageDialog.vue` — 内嵌 Panel
- `frontend/src/components/workorder/TimeCategoryManageDialog.vue` — 内嵌 Panel
- `frontend/src/components/workorder/CostCategoryManageDialog.vue` — 内嵌 Panel
- `frontend/src/router/routes.ts` — 新增 config 路由 + 旧路由改 redirect
- `frontend/src/components/AppSidebar.vue` — 「管理」组改为 用户/角色/团队/配置中心 + activeMenu 归并

**测试(新建/更新):**
- `frontend/tests/unit/CustomFieldsView.spec.ts`(更新或新建:lockedEntity 行为)
- `frontend/tests/unit/ConfigConsoleView.spec.ts`(新建)
- `frontend/tests/unit/configAggregateViews.spec.ts`(新建:4 聚合页 tab 渲染)
- `frontend/tests/unit/AppSidebar.spec.ts`(更新:新菜单结构)
- `frontend/tests/unit/configRoutes.spec.ts`(新建:旧路由 redirect)

所有命令在 `frontend/` 目录下执行。

---

## Phase A — 基础组件改造

### Task 1: CustomFieldsView 支持单实体锁定与嵌入

**Files:**
- Modify: `frontend/src/views/settings/CustomFieldsView.vue`
- Test: `frontend/tests/unit/CustomFieldsView.spec.ts`

- [ ] **Step 1: 写失败测试**

新建/追加 `frontend/tests/unit/CustomFieldsView.spec.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'

vi.mock('@/api/customFields', () => ({
  listCustomFields: vi.fn().mockResolvedValue([]),
  createCustomField: vi.fn(),
  updateCustomField: vi.fn(),
  archiveCustomField: vi.fn(),
  restoreCustomField: vi.fn(),
  deleteCustomField: vi.fn(),
  reorderCustomFields: vi.fn(),
}))
import { listCustomFields } from '@/api/customFields'

describe('CustomFieldsView lockedEntity', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('lockedEntity 时隐藏实体选择器并按该实体加载', async () => {
    const wrapper = mount(CustomFieldsView, {
      props: { lockedEntity: 'asset', embedded: true },
      global: { stubs: { teleport: true } },
    })
    await Promise.resolve()
    // 实体下拉被隐藏
    expect(wrapper.find('.toolbar .el-select').exists()).toBe(false)
    // 嵌入态不渲染页标题
    expect(wrapper.find('.page-title').exists()).toBe(false)
    // 按锁定实体加载
    expect(listCustomFields).toHaveBeenCalledWith('asset', true)
  })

  it('无 lockedEntity 时仍渲染实体选择器且默认 work_order', async () => {
    const wrapper = mount(CustomFieldsView, { global: { stubs: { teleport: true } } })
    await Promise.resolve()
    expect(wrapper.find('.toolbar .el-select').exists()).toBe(true)
    expect(listCustomFields).toHaveBeenCalledWith('work_order', true)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run tests/unit/CustomFieldsView.spec.ts`
Expected: FAIL(props 未定义 / 选择器仍存在 / page-title 仍渲染)

- [ ] **Step 3: 改 CustomFieldsView 加 props**

在 `<script setup>` 中,`const auth = useAuthStore()` 上方插入 props 定义,并改 `entityType` 初值。当前(`CustomFieldsView.vue:37-42`):

```ts
const auth = useAuthStore()
const canEdit = ref(auth.hasPermission('company.settings'))
...
const entityType = ref<CustomFieldEntity>('work_order')
```

改为:

```ts
const props = withDefaults(
  defineProps<{ lockedEntity?: CustomFieldEntity; embedded?: boolean }>(),
  { lockedEntity: undefined, embedded: false },
)

const auth = useAuthStore()
const canEdit = ref(auth.hasPermission('company.settings'))
...
const entityType = ref<CustomFieldEntity>(props.lockedEntity ?? 'work_order')
```

- [ ] **Step 4: 改模板隐藏标题与选择器**

`CustomFieldsView.vue:246` 页标题加 `v-if`:

```html
<h2 v-if="!embedded" class="page-title">自定义字段</h2>
```

`CustomFieldsView.vue:250-261` 的 `<el-select>` 整块加 `v-if="!lockedEntity"`:

```html
<el-select
  v-if="!lockedEntity"
  v-model="entityType"
  style="width: 160px"
  @change="onEntityChange"
>
  <el-option v-for="opt in ENTITY_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
</el-select>
```

> `lockedEntity`/`embedded` 在模板中通过编译器宏自动解构可用;若 lint 报未定义,改用 `props.lockedEntity` / `props.embedded`。

- [ ] **Step 5: 运行测试确认通过**

Run: `npx vitest run tests/unit/CustomFieldsView.spec.ts`
Expected: PASS

- [ ] **Step 6: typecheck**

Run: `npm run typecheck`
Expected: 无错误

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/settings/CustomFieldsView.vue frontend/tests/unit/CustomFieldsView.spec.ts
git commit -m "feat(config): CustomFieldsView 支持 lockedEntity/embedded 单实体复用"
```

---

### Task 2: 抽取工单分类管理面板

**Files:**
- Create: `frontend/src/components/maintenance/WorkOrderCategoryManagePanel.vue`
- Modify: `frontend/src/components/maintenance/WorkOrderCategoryManageDialog.vue`
- Test: `frontend/tests/unit/WorkOrderCategoryManagePanel.spec.ts`

> **做法**:把 `WorkOrderCategoryManageDialog.vue` 里「列表 + 新建/编辑表单」的脚本与模板主体整体搬进 `WorkOrderCategoryManagePanel.vue`(去掉最外层 `el-dialog` 列表壳,保留内层新建表单的 `el-dialog`)。Dialog 改为壳:`<el-dialog>` 内放 `<WorkOrderCategoryManagePanel v-if="visible" />`,用 `v-if` 让每次打开重挂载触发加载。

- [ ] **Step 1: 写失败测试**

`frontend/tests/unit/WorkOrderCategoryManagePanel.spec.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorkOrderCategoryManagePanel from '@/components/maintenance/WorkOrderCategoryManagePanel.vue'

vi.mock('@/api/workOrderCategories', () => ({
  listWorkOrderCategories: vi.fn().mockResolvedValue([
    { id: '1', name: '机械', description: '' },
  ]),
  createWorkOrderCategory: vi.fn(),
  updateWorkOrderCategory: vi.fn(),
  deleteWorkOrderCategory: vi.fn(),
}))
import { listWorkOrderCategories } from '@/api/workOrderCategories'

describe('WorkOrderCategoryManagePanel', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('挂载即加载分类列表', async () => {
    const wrapper = mount(WorkOrderCategoryManagePanel, { global: { stubs: { teleport: true } } })
    await Promise.resolve(); await Promise.resolve()
    expect(listWorkOrderCategories).toHaveBeenCalled()
    expect(wrapper.text()).toContain('机械')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/WorkOrderCategoryManagePanel.spec.ts`
Expected: FAIL(组件不存在)

- [ ] **Step 3: 创建 Panel**

读 `WorkOrderCategoryManageDialog.vue` 全文,把其中:
- 所有 `import`、`ref`、列表加载 `load()`、新建/编辑/删除逻辑、内层新建表单 `el-dialog(formVisible)` —— 原样搬入 Panel;
- **删除** props `visible`、`emit('update:visible')`、最外层列表 `el-dialog`(`:model-value="visible"`)壳;
- 列表 `el-table` 与工具栏「新建分类」按钮直接作为 Panel 根模板;
- 把原 Dialog 的 `onMounted`/`watch(visible)` 触发加载改为 Panel 顶层 `onMounted(load)`。

Panel 模板骨架:

```html
<template>
  <div class="wo-category-panel">
    <div class="panel-toolbar">
      <el-button type="primary" @click="openCreate">新建分类</el-button>
    </div>
    <el-table v-loading="loading" :data="categories" border style="width: 100%; margin-top: 12px">
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="description" label="描述" min-width="200" />
      <!-- 原 Dialog 的操作列原样保留 -->
    </el-table>
    <!-- 内层新建/编辑表单 el-dialog(formVisible) 原样保留 -->
  </div>
</template>
```

- [ ] **Step 4: Dialog 改为壳复用 Panel**

`WorkOrderCategoryManageDialog.vue` 整体改为:

```html
<script setup lang="ts">
import WorkOrderCategoryManagePanel from './WorkOrderCategoryManagePanel.vue'
const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (e: 'update:visible', v: boolean): void }>()
function close() { emit('update:visible', false) }
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    title="工单分类管理"
    width="640px"
    @update:model-value="close"
  >
    <WorkOrderCategoryManagePanel v-if="props.visible" />
  </el-dialog>
</template>
```

> 若原 Dialog 对外还 emit 了 `changed`/`refresh` 之类事件,保留这些 emit 并由 Panel 透传(Panel 增加对应 `defineEmits` 并在 CRUD 成功后 emit;Dialog 用 `@changed` 转发)。先 grep 原 Dialog 的 `emit(` 全集确认。

- [ ] **Step 5: 运行 Panel 测试 + 原 Dialog 测试**

Run: `npx vitest run tests/unit/WorkOrderCategoryManagePanel.spec.ts tests/unit/WorkOrderCategoryManageDialog.spec.ts`
Expected: PASS(若不存在 Dialog 的 spec 则仅前者)

- [ ] **Step 6: typecheck + 全量 test**

Run: `npm run typecheck && npx vitest run`
Expected: 全绿

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/maintenance/WorkOrderCategoryManagePanel.vue frontend/src/components/maintenance/WorkOrderCategoryManageDialog.vue frontend/tests/unit/WorkOrderCategoryManagePanel.spec.ts
git commit -m "refactor(wo): 抽取工单分类管理面板供聚合页与弹窗复用"
```

---

### Task 3: 抽取工时分类管理面板

**Files:**
- Create: `frontend/src/components/workorder/TimeCategoryManagePanel.vue`
- Modify: `frontend/src/components/workorder/TimeCategoryManageDialog.vue`
- Test: `frontend/tests/unit/TimeCategoryManagePanel.spec.ts`

> 与 Task 2 完全同构,只把 `WorkOrderCategory`→`TimeCategory`、`api/workOrderCategories`→`api/timeCategories`、组件名替换。

- [ ] **Step 1: 写失败测试**

`frontend/tests/unit/TimeCategoryManagePanel.spec.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TimeCategoryManagePanel from '@/components/workorder/TimeCategoryManagePanel.vue'

vi.mock('@/api/timeCategories', () => ({
  listTimeCategories: vi.fn().mockResolvedValue([{ id: '1', name: '正常工时', description: '' }]),
  createTimeCategory: vi.fn(),
  updateTimeCategory: vi.fn(),
  deleteTimeCategory: vi.fn(),
}))
import { listTimeCategories } from '@/api/timeCategories'

describe('TimeCategoryManagePanel', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })
  it('挂载即加载工时分类', async () => {
    const wrapper = mount(TimeCategoryManagePanel, { global: { stubs: { teleport: true } } })
    await Promise.resolve(); await Promise.resolve()
    expect(listTimeCategories).toHaveBeenCalled()
    expect(wrapper.text()).toContain('正常工时')
  })
})
```

> 注意:先 `grep -n "export" frontend/src/api/timeCategories.ts` 核对真实导出函数名,替换 mock 键。

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/TimeCategoryManagePanel.spec.ts`
Expected: FAIL(组件不存在)

- [ ] **Step 3: 创建 Panel**(同 Task 2 Step 3 做法,源文件 `TimeCategoryManageDialog.vue`)

- [ ] **Step 4: Dialog 改为壳复用 Panel**(同 Task 2 Step 4,标题改「工时分类管理」)

- [ ] **Step 5: 运行测试**

Run: `npx vitest run tests/unit/TimeCategoryManagePanel.spec.ts`
Expected: PASS

- [ ] **Step 6: typecheck + 全量 test**

Run: `npm run typecheck && npx vitest run`
Expected: 全绿

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/workorder/TimeCategoryManagePanel.vue frontend/src/components/workorder/TimeCategoryManageDialog.vue frontend/tests/unit/TimeCategoryManagePanel.spec.ts
git commit -m "refactor(wo): 抽取工时分类管理面板"
```

---

### Task 4: 抽取成本分类管理面板

**Files:**
- Create: `frontend/src/components/workorder/CostCategoryManagePanel.vue`
- Modify: `frontend/src/components/workorder/CostCategoryManageDialog.vue`
- Test: `frontend/tests/unit/CostCategoryManagePanel.spec.ts`

> 与 Task 3 同构,`Time`→`Cost`、`api/timeCategories`→`api/costCategories`。已存在 `CostCategoryManageDialog.spec.ts`,改后须保持其绿。

- [ ] **Step 1: 写失败测试**(同 Task 3 模板,替换 Cost/`api/costCategories`,先核对导出名)

`frontend/tests/unit/CostCategoryManagePanel.spec.ts`(结构同上,mock `@/api/costCategories`,断言加载与渲染样例分类名)。

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/CostCategoryManagePanel.spec.ts`
Expected: FAIL

- [ ] **Step 3: 创建 Panel**(源 `CostCategoryManageDialog.vue`)

- [ ] **Step 4: Dialog 改为壳复用 Panel**(标题「成本分类管理」)

- [ ] **Step 5: 运行 Panel + 既有 Dialog 测试**

Run: `npx vitest run tests/unit/CostCategoryManagePanel.spec.ts tests/unit/CostCategoryManageDialog.spec.ts`
Expected: PASS(既有 Dialog spec 仍绿,必要时按壳化结构微调其断言)

- [ ] **Step 6: typecheck + 全量 test**

Run: `npm run typecheck && npx vitest run`
Expected: 全绿

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/workorder/CostCategoryManagePanel.vue frontend/src/components/workorder/CostCategoryManageDialog.vue frontend/tests/unit/CostCategoryManagePanel.spec.ts frontend/tests/unit/CostCategoryManageDialog.spec.ts
git commit -m "refactor(wo): 抽取成本分类管理面板"
```

---

## Phase B — 模块聚合页

> 聚合页通用约定:薄壳 `el-tabs`,`v-model="activeTab"` 与 `route.query.tab` 双向同步(进入时读 query,切换时 `router.replace` 写 query,便于旧 URL redirect 落到指定 tab)。tab 内容直接渲染既有 view/Panel 组件。所有既有 view 组件内部自带页标题与 padding——嵌入时可接受(各 tab 内一个小标题),不强制去除;`CustomFieldsView` 用 `embedded` 去标题。

### Task 5: SOP 配置聚合页

**Files:**
- Create: `frontend/src/views/admin/config/SopConfigView.vue`
- Test: `frontend/tests/unit/configAggregateViews.spec.ts`

- [ ] **Step 1: 写失败测试**(本 spec 文件 Task 5–8 共用,先建 SOP 用例)

`frontend/tests/unit/configAggregateViews.spec.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SopConfigView from '@/views/admin/config/SopConfigView.vue'

// 子 view 用 stub,聚合页只验证 tab 骨架
const stubs = {
  FieldManageView: { template: '<div class="stub-field-manage" />' },
  HeadingRulesView: { template: '<div class="stub-heading-rules" />' },
}

function mountWith(comp: unknown, query: Record<string, string> = {}) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: comp as never }] })
  router.push({ path: '/', query })
  return router.isReady().then(() =>
    mount(comp as never, { global: { plugins: [createPinia(), router], stubs } }),
  )
}

describe('SopConfigView', () => {
  it('渲染程序字段与标题字典两个 tab', async () => {
    const wrapper = await mountWith(SopConfigView)
    const labels = wrapper.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['程序字段', '标题字典']))
  })
  it('按 query.tab 选中 heading-rules', async () => {
    const wrapper = await mountWith(SopConfigView, { tab: 'heading-rules' })
    expect(wrapper.find('.el-tabs__item.is-active').text()).toBe('标题字典')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/configAggregateViews.spec.ts`
Expected: FAIL(组件不存在)

- [ ] **Step 3: 创建 SopConfigView**

```html
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import FieldManageView from '@/views/settings/FieldManageView.vue'
import HeadingRulesView from '@/views/settings/HeadingRulesView.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref<string>((route.query.tab as string) || 'fields')
watch(activeTab, (t) => router.replace({ query: { ...route.query, tab: t } }))
</script>

<template>
  <div class="config-aggregate">
    <h2 class="page-title">SOP 配置</h2>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="程序字段" name="fields"><FieldManageView /></el-tab-pane>
      <el-tab-pane label="标题字典" name="heading-rules"><HeadingRulesView /></el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate { padding: 20px 24px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0 0 16px; color: var(--text-primary); }
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run tests/unit/configAggregateViews.spec.ts`
Expected: SopConfigView 两用例 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/admin/config/SopConfigView.vue frontend/tests/unit/configAggregateViews.spec.ts
git commit -m "feat(config): SOP 配置聚合页(程序字段+标题字典)"
```

---

### Task 6: 工单配置聚合页

**Files:**
- Create: `frontend/src/views/admin/config/WorkOrderConfigView.vue`
- Test: `frontend/tests/unit/configAggregateViews.spec.ts`(追加)

- [ ] **Step 1: 追加失败测试**

在 `configAggregateViews.spec.ts` 顶部 import 增加 `WorkOrderConfigView`,stubs 增加 `WorkOrderFieldsView`、`CustomFieldsView`、三个 `*ManagePanel`,追加:

```ts
import WorkOrderConfigView from '@/views/admin/config/WorkOrderConfigView.vue'
// stubs 追加:
//   WorkOrderFieldsView, CustomFieldsView,
//   WorkOrderCategoryManagePanel, TimeCategoryManagePanel, CostCategoryManagePanel

describe('WorkOrderConfigView', () => {
  it('渲染五个 tab', async () => {
    const wrapper = await mountWith(WorkOrderConfigView)
    const labels = wrapper.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(
      expect.arrayContaining(['表单字段', '自定义字段', '工单分类', '工时分类', '成本分类']),
    )
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/configAggregateViews.spec.ts`
Expected: WorkOrderConfigView 用例 FAIL

- [ ] **Step 3: 创建 WorkOrderConfigView**

```html
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import WorkOrderFieldsView from '@/views/settings/WorkOrderFieldsView.vue'
import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'
import WorkOrderCategoryManagePanel from '@/components/maintenance/WorkOrderCategoryManagePanel.vue'
import TimeCategoryManagePanel from '@/components/workorder/TimeCategoryManagePanel.vue'
import CostCategoryManagePanel from '@/components/workorder/CostCategoryManagePanel.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref<string>((route.query.tab as string) || 'form-fields')
watch(activeTab, (t) => router.replace({ query: { ...route.query, tab: t } }))
</script>

<template>
  <div class="config-aggregate">
    <h2 class="page-title">工单配置</h2>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="表单字段" name="form-fields"><WorkOrderFieldsView /></el-tab-pane>
      <el-tab-pane label="自定义字段" name="custom-fields">
        <CustomFieldsView locked-entity="work_order" embedded />
      </el-tab-pane>
      <el-tab-pane label="工单分类" name="categories"><WorkOrderCategoryManagePanel /></el-tab-pane>
      <el-tab-pane label="工时分类" name="time-categories"><TimeCategoryManagePanel /></el-tab-pane>
      <el-tab-pane label="成本分类" name="cost-categories"><CostCategoryManagePanel /></el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate { padding: 20px 24px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0 0 16px; color: var(--text-primary); }
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run tests/unit/configAggregateViews.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/admin/config/WorkOrderConfigView.vue frontend/tests/unit/configAggregateViews.spec.ts
git commit -m "feat(config): 工单配置聚合页(表单字段+自定义字段+三类分类)"
```

---

### Task 7: 请求配置聚合页

**Files:**
- Create: `frontend/src/views/admin/config/RequestConfigView.vue`
- Test: `frontend/tests/unit/configAggregateViews.spec.ts`(追加)

- [ ] **Step 1: 追加失败测试**

import `RequestConfigView`,stubs 加 `RequestFieldsView`(`CustomFieldsView` 已 stub),追加:

```ts
import RequestConfigView from '@/views/admin/config/RequestConfigView.vue'

describe('RequestConfigView', () => {
  it('渲染表单字段与自定义字段两个 tab', async () => {
    const wrapper = await mountWith(RequestConfigView)
    const labels = wrapper.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['表单字段', '自定义字段']))
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/configAggregateViews.spec.ts`
Expected: RequestConfigView 用例 FAIL

- [ ] **Step 3: 创建 RequestConfigView**

```html
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import RequestFieldsView from '@/views/settings/RequestFieldsView.vue'
import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref<string>((route.query.tab as string) || 'form-fields')
watch(activeTab, (t) => router.replace({ query: { ...route.query, tab: t } }))
</script>

<template>
  <div class="config-aggregate">
    <h2 class="page-title">请求配置</h2>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="表单字段" name="form-fields"><RequestFieldsView /></el-tab-pane>
      <el-tab-pane label="自定义字段" name="custom-fields">
        <CustomFieldsView locked-entity="request" embedded />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate { padding: 20px 24px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0 0 16px; color: var(--text-primary); }
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run tests/unit/configAggregateViews.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/admin/config/RequestConfigView.vue frontend/tests/unit/configAggregateViews.spec.ts
git commit -m "feat(config): 请求配置聚合页(表单字段+自定义字段)"
```

---

### Task 8: 统一自定义字段聚合页(资产/位置/备件)

**Files:**
- Create: `frontend/src/views/admin/config/CustomFieldsConfigView.vue`
- Test: `frontend/tests/unit/configAggregateViews.spec.ts`(追加)

- [ ] **Step 1: 追加失败测试**

import `CustomFieldsConfigView`(`CustomFieldsView` 已 stub),追加:

```ts
import CustomFieldsConfigView from '@/views/admin/config/CustomFieldsConfigView.vue'

describe('CustomFieldsConfigView', () => {
  it('渲染资产/位置/备件三个 tab', async () => {
    const wrapper = await mountWith(CustomFieldsConfigView)
    const labels = wrapper.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['资产', '位置', '备件']))
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/configAggregateViews.spec.ts`
Expected: FAIL

- [ ] **Step 3: 创建 CustomFieldsConfigView**

```html
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref<string>((route.query.tab as string) || 'asset')
watch(activeTab, (t) => router.replace({ query: { ...route.query, tab: t } }))
</script>

<template>
  <div class="config-aggregate">
    <h2 class="page-title">自定义字段</h2>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="资产" name="asset">
        <CustomFieldsView locked-entity="asset" embedded />
      </el-tab-pane>
      <el-tab-pane label="位置" name="location">
        <CustomFieldsView locked-entity="location" embedded />
      </el-tab-pane>
      <el-tab-pane label="备件" name="part">
        <CustomFieldsView locked-entity="part" embedded />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate { padding: 20px 24px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0 0 16px; color: var(--text-primary); }
</style>
```

> 每个 tab 用独立 `CustomFieldsView` 实例 + 不同 `locked-entity`,互不串数据(el-tab-pane 默认懒渲染/缓存,组件各自 `onMounted` 按自身实体加载)。

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run tests/unit/configAggregateViews.spec.ts`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/admin/config/CustomFieldsConfigView.vue frontend/tests/unit/configAggregateViews.spec.ts
git commit -m "feat(config): 统一自定义字段聚合页(资产/位置/备件)"
```

---

## Phase C — Hub、路由、菜单

### Task 9: 配置中心 Hub 总览页

**Files:**
- Create: `frontend/src/views/admin/config/ConfigConsoleView.vue`
- Test: `frontend/tests/unit/ConfigConsoleView.spec.ts`

- [ ] **Step 1: 写失败测试**

`frontend/tests/unit/ConfigConsoleView.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ConfigConsoleView from '@/views/admin/config/ConfigConsoleView.vue'

function mountHub() {
  return mount(ConfigConsoleView, {
    global: { plugins: [createPinia()], stubs: { 'router-link': RouterLinkStub } },
  })
}

describe('ConfigConsoleView', () => {
  it('渲染六个部署阶段区块', () => {
    const wrapper = mountHub()
    const text = wrapper.text()
    for (const t of ['组织基础', '人员权限', '全局参数', '业务模块', '自动化', '运维']) {
      expect(text).toContain(t)
    }
  })
  it('业务模块区块含四个聚合页入口', () => {
    const wrapper = mountHub()
    const targets = wrapper.findAllComponents(RouterLinkStub).map((l) => l.props('to'))
    for (const to of ['/admin/config/sop', '/admin/config/work-order', '/admin/config/request', '/admin/config/custom-fields']) {
      expect(targets).toContain(to)
    }
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/ConfigConsoleView.spec.ts`
Expected: FAIL

- [ ] **Step 3: 创建 ConfigConsoleView**

按阶段分区块,每块卡片含若干 `router-link` 入口 + 一句说明。用纯数据数组驱动:

```html
<script setup lang="ts">
interface Entry { label: string; to: string; hint?: string }
interface Stage { no: string; title: string; desc: string; entries: Entry[] }

const stages: Stage[] = [
  { no: '①', title: '组织基础', desc: '先决定启用哪些业务模块,再配组织与货币', entries: [
    { label: '公司设置 · 模块开关', to: '/admin/company' },
    { label: '货币', to: '/admin/currencies' },
  ]},
  { no: '②', title: '人员权限', desc: '角色 → 团队 → 用户,先有角色再分配', entries: [
    { label: '角色', to: '/admin/roles' },
    { label: '团队', to: '/admin/teams' },
    { label: '用户', to: '/admin/users' },
  ]},
  { no: '③', title: '全局参数', desc: '审批流、版本控制等全局开关,影响各模块行为', entries: [
    { label: '系统设置', to: '/admin/settings' },
  ]},
  { no: '④', title: '业务模块', desc: '为已启用的模块配置字段、表单与分类', entries: [
    { label: 'SOP 配置', to: '/admin/config/sop' },
    { label: '工单配置', to: '/admin/config/work-order' },
    { label: '请求配置', to: '/admin/config/request' },
    { label: '自定义字段(资产/库存)', to: '/admin/config/custom-fields' },
  ]},
  { no: '⑤', title: '自动化', desc: '实体就绪后再配自动化规则', entries: [
    { label: '工作流', to: '/admin/workflows' },
  ]},
  { no: '⑥', title: '运维', desc: '数据导入、文件与审计', entries: [
    { label: '数据导入', to: '/admin/imports' },
    { label: '文件库', to: '/admin/files' },
    { label: '审计日志', to: '/admin/audit-logs' },
  ]},
]
</script>

<template>
  <div class="config-console">
    <h2 class="page-title">配置中心</h2>
    <p class="console-hint">初次部署建议从上往下依次配置;日常维护可直接点入对应模块。</p>
    <div class="stage-grid">
      <section v-for="s in stages" :key="s.no" class="stage-card">
        <header class="stage-head"><span class="stage-no">{{ s.no }}</span>{{ s.title }}</header>
        <p class="stage-desc">{{ s.desc }}</p>
        <ul class="stage-entries">
          <li v-for="e in s.entries" :key="e.to">
            <router-link :to="e.to">{{ e.label }}</router-link>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.config-console { padding: 20px 24px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0 0 6px; color: var(--text-primary); }
.console-hint { margin: 0 0 20px; color: var(--text-tertiary); font-size: 13px; }
.stage-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.stage-card { border: 1px solid var(--border-subtle); border-radius: 8px; padding: 16px; background: var(--bg-surface); }
.stage-head { font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
.stage-no { color: var(--accent); font-weight: 700; }
.stage-desc { margin: 8px 0 12px; font-size: 12px; color: var(--text-tertiary); }
.stage-entries { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.stage-entries a { color: var(--accent); text-decoration: none; font-size: 14px; }
.stage-entries a:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run tests/unit/ConfigConsoleView.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/admin/config/ConfigConsoleView.vue frontend/tests/unit/ConfigConsoleView.spec.ts
git commit -m "feat(config): 部署导向配置中心总览 Hub"
```

---

### Task 10: 路由新增与旧路由 redirect

**Files:**
- Modify: `frontend/src/router/routes.ts`
- Test: `frontend/tests/unit/configRoutes.spec.ts`

- [ ] **Step 1: 写失败测试**

`frontend/tests/unit/configRoutes.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routes } from '@/router/routes'

function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

describe('config 路由', () => {
  it('新增聚合页与 Hub 路由可解析', async () => {
    const r = makeRouter()
    for (const p of ['/admin/config', '/admin/config/sop', '/admin/config/work-order', '/admin/config/request', '/admin/config/custom-fields']) {
      await r.push(p)
      expect(r.currentRoute.value.matched.length).toBeGreaterThan(0)
    }
  })

  it('旧路由 redirect 到聚合页对应 tab', async () => {
    const cases: [string, string, string | undefined][] = [
      ['/admin/fields', '/admin/config/sop', 'fields'],
      ['/admin/heading-rules', '/admin/config/sop', 'heading-rules'],
      ['/admin/work-order-fields', '/admin/config/work-order', 'form-fields'],
      ['/admin/request-fields', '/admin/config/request', 'form-fields'],
      ['/admin/custom-fields', '/admin/config/custom-fields', undefined],
    ]
    const r = makeRouter()
    for (const [from, path, tab] of cases) {
      await r.push(from)
      expect(r.currentRoute.value.path).toBe(path)
      if (tab) expect(r.currentRoute.value.query.tab).toBe(tab)
    }
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/configRoutes.spec.ts`
Expected: FAIL

- [ ] **Step 3: 新增 config 路由块**

在 `routes.ts` 数组中(`/admin/settings` 路由附近)新增:

```ts
  {
    path: '/admin/config',
    name: 'config-console',
    component: () => import('@/views/admin/config/ConfigConsoleView.vue'),
    meta: { title: '配置中心', requiresAuth: true },
  },
  {
    path: '/admin/config/sop',
    name: 'config-sop',
    component: () => import('@/views/admin/config/SopConfigView.vue'),
    meta: { title: 'SOP 配置', requiresAuth: true },
  },
  {
    path: '/admin/config/work-order',
    name: 'config-work-order',
    component: () => import('@/views/admin/config/WorkOrderConfigView.vue'),
    meta: { title: '工单配置', requiresAuth: true },
  },
  {
    path: '/admin/config/request',
    name: 'config-request',
    component: () => import('@/views/admin/config/RequestConfigView.vue'),
    meta: { title: '请求配置', requiresAuth: true },
  },
  {
    path: '/admin/config/custom-fields',
    name: 'config-custom-fields',
    component: () => import('@/views/admin/config/CustomFieldsConfigView.vue'),
    meta: { title: '自定义字段', requiresAuth: true },
  },
```

- [ ] **Step 4: 旧路由改 redirect**

把这些既有路由记录的 `component`/`name`/`meta` 整体替换为 `redirect`(保留 `path`):

```ts
  { path: '/admin/fields', redirect: { path: '/admin/config/sop', query: { tab: 'fields' } } },
  { path: '/admin/heading-rules', redirect: { path: '/admin/config/sop', query: { tab: 'heading-rules' } } },
  { path: '/admin/work-order-fields', redirect: { path: '/admin/config/work-order', query: { tab: 'form-fields' } } },
  { path: '/admin/request-fields', redirect: { path: '/admin/config/request', query: { tab: 'form-fields' } } },
  { path: '/admin/custom-fields', redirect: '/admin/config/custom-fields' },
```

> 既有指向旧路径的别名 redirect(如 `/settings/fields → /admin/fields`、`/settings/heading-rules → /admin/heading-rules`)保留不动——它们会二次跳转到新目标,链路仍通。原 `FieldManageView`/`HeadingRulesView`/`RequestFieldsView`/`WorkOrderFieldsView`/`CustomFieldsView` 组件不再被路由直接挂载,改由聚合页 import,文件保留。

- [ ] **Step 5: 运行确认通过 + typecheck**

Run: `npx vitest run tests/unit/configRoutes.spec.ts && npm run typecheck`
Expected: PASS,无类型错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/router/routes.ts frontend/tests/unit/configRoutes.spec.ts
git commit -m "feat(config): 新增配置中心路由并将旧字段路由重定向到聚合页 tab"
```

---

### Task 11: 侧栏菜单重排

**Files:**
- Modify: `frontend/src/components/AppSidebar.vue`
- Test: `frontend/tests/unit/AppSidebar.spec.ts`

> 起点是工作区里已落地的「按职责四拆」改动。本任务把「管理」组替换为:用户 / 角色 / 团队 / 配置中心(单入口指向 Hub),并清掉四拆引入但不再需要的子分组与图标。组织配置、表单与字段、自动化与数据、审计等改由 Hub 承载。

- [ ] **Step 1: 更新/写测试**

先 `cat frontend/tests/unit/AppSidebar.spec.ts` 看现有断言。新增/调整断言:

```ts
it('管理组含配置中心入口,不再有系统配置/表单与字段子分组', () => {
  // 以现有 spec 的挂载方式为准(沿用其 mount helper / store mock)
  // 断言渲染出 '配置中心' 文本,且不出现 '系统配置'/'表单与字段'/'自动化与数据'
  expect(text).toContain('配置中心')
  expect(text).not.toContain('系统配置')
  expect(text).not.toContain('表单与字段')
})
```

> 具体挂载样板沿用文件现有用例,只增/改与「管理」组相关的断言。若现有用例断言了旧的「系统配置」等文本,一并改为新结构。

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/AppSidebar.spec.ts`
Expected: FAIL(新断言未满足)

- [ ] **Step 3: 改 AppSidebar 的「管理」组**

把 `rawGroups` 中 `label: '管理'` 的 `entries` 整体替换为:

```ts
  {
    label: '管理',
    entries: [
      {
        label: '人员与权限',
        icon: User,
        items: [
          { label: '用户', path: '/admin/users', icon: User },
          { label: '角色', path: '/admin/roles', icon: UserFilled },
          { label: '团队', path: '/admin/teams', icon: Connection },
        ],
      },
      { label: '配置中心', path: '/admin/config', icon: Setting },
    ],
  },
```

清理 import:删除四拆/旧结构引入但本组不再使用的图标(逐个核对 `rawGroups` 与 `orgConfigItems`/`analyticsItems` 实际仍用到的图标,删除其余;`Setting` 仍用于配置中心入口,保留)。`orgConfigItems` computed 若不再被任何 entries 引用,一并删除。

- [ ] **Step 4: activeMenu 归并**

`activeMenu` computed 的 `if (p.startsWith('/admin/')) return p` 已覆盖 `/admin/config*`;确认其位置在其它 `/admin/` 分支之前即可,无需新增。若「配置中心」单项需高亮,补:

```ts
  if (p.startsWith('/admin/config')) return '/admin/config'
```

放在 `if (p.startsWith('/admin/'))` 之前。

- [ ] **Step 5: 运行测试 + typecheck + lint**

Run: `npx vitest run tests/unit/AppSidebar.spec.ts && npm run typecheck && npm run lint`
Expected: PASS,无类型/lint 错误(未使用 import 会被 lint 拦截,据此清干净)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AppSidebar.vue frontend/tests/unit/AppSidebar.spec.ts
git commit -m "feat(config): 侧栏管理组改为人员权限+配置中心单入口"
```

---

## Phase D — 收口验证

### Task 12: 全量校验与运行态走查

**Files:** 无(验证 + 文档)

- [ ] **Step 1: 全量门禁**

Run: `npm run typecheck && npm run lint && npx vitest run`
Expected: 三者全绿

- [ ] **Step 2: 运行态走查**

用 `running-smartsop-dev` skill 启动 dev,以管理员登录,逐项确认:
- 侧栏「管理 → 配置中心」可达,Hub 渲染六阶段区块;
- 业务模块区块四个入口分别进入 SOP/工单/请求/自定义字段聚合页,各 tab 切换与 CRUD 正常;
- 工单配置页「工单分类/工时分类/成本分类」tab 能增删改,且工单业务页内原弹窗仍正常;
- 旧 URL 手敲验证:`/admin/fields`、`/admin/work-order-fields`、`/admin/request-fields`、`/admin/custom-fields`、`/admin/heading-rules` 均 redirect 到正确聚合页与 tab;
- 公司设置关闭某模块开关(如 `show_requests`)后,相关入口随 `hiddenPaths` 行为表现符合预期。

- [ ] **Step 3: 收尾 commit(如走查触发微调)**

```bash
git add -A
git commit -m "chore(config): 运行态走查修正与收口"
```

---

## Self-Review(已对照 spec 检查)

- **Spec 覆盖**:Hub(Task 9)、4 聚合页(Task 5–8)、CustomFieldsView 预筛(Task 1)、3 分类面板抽取(Task 2–4)、路由+redirect(Task 10)、菜单重排(Task 11)、验证(Task 12)——spec 各节均有对应任务。
- **非目标**:无完成度徽章、无 wizard、无后端改动——计划内未出现。
- **类型/命名一致**:`lockedEntity`/`embedded` props、tab `name`(`fields`/`heading-rules`/`form-fields`/`custom-fields`/`categories`/`time-categories`/`cost-categories`/`asset`/`location`/`part`)、路由 `/admin/config/*` 在各任务间一致。
- **已知需在执行时现场核对的点**(非占位符,是真实代码依赖):各分类 `api/*Categories.ts` 的导出函数名(Task 3/4 已注明先 grep);`AppSidebar.spec.ts` 与各 `*Dialog.spec.ts` 现有断言样板(Task 11/4 已注明沿用)。
