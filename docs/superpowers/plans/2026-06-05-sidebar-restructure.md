# 侧边栏重构（方案 B）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重排侧边栏分组与命名以对齐用户心智，合并配置类入口为可折叠「管理」组，将多备件套件下沉为备件库存页内 Tab，并统一错配的路由前缀（旧路径全量重定向兜底）。

**Architecture:** 纯前端改造。路由层在 `router/index.ts` 引入新路径并对每个旧路径登记 `redirect`；`AppSidebar.vue` 用「组 → 子分组(el-sub-menu) → 项」三级数据模型重排菜单，管理组折叠承载；新建 `PartsHubView.vue` 以 `el-tabs` 路由驱动承载备件/套件两视图，原视图加 `embedded` prop 复用。内链仅 `AppSidebar.vue` 与 `AppTopBar.vue` 两处（已 grep 确认无其它 `router.push`/`router-link` 指向变更路径）。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript、Vue Router 4、Element Plus（`el-menu`/`el-sub-menu`/`el-tabs`）、Pinia、Vitest + @vue/test-utils。

**基线：** main = `ade4380`，前端 `npm run test` = 129 文件 / 826 测试全绿。须全程保持绿。

**前置（执行时，不计入任务）：** 用 superpowers:using-git-worktrees 在 `ade4380` 基础上建隔离 worktree + 分支（建议 `feat/sidebar-restructure`）。所有命令在该 worktree 的 `frontend/` 下执行。

---

## 路由变更总表（Task 1 依据）

| 项 | 旧路径 | 新路径 | 组件 |
|---|---|---|---|
| 文件夹 | `/folders` | `/procedures/folders` | FolderManageView |
| 资产 | `/maindata/assets` | `/assets` | AssetsView |
| 位置 | `/maindata/locations` | `/assets/locations` | LocationsView |
| 多备件套件 | `/inventory/multi-parts` | `/inventory/parts/kits` | PartsHubView(套件 tab) |
| 客户 | `/inventory/customers` | `/maintenance/customers` | CustomersView |
| 用户 | `/platform/users` | `/admin/users` | UsersView |
| 角色 | `/platform/roles` | `/admin/roles` | RolesView |
| 团队 | `/platform/teams` | `/admin/teams` | TeamsView |
| 公司设置 | `/platform/settings` | `/admin/company` | CompanySettingsView |
| 货币 | `/platform/currencies` | `/admin/currencies` | CurrenciesView |
| 系统设置 | `/settings` | `/admin/settings` | SettingsView |
| 字段管理 | `/settings/fields` | `/admin/fields` | FieldManageView |
| 标题字典 | `/settings/heading-rules` | `/admin/heading-rules` | HeadingRulesView |
| 审计日志 | `/audit-logs` | `/admin/audit-logs` | AuditLogsView |

**不变：** `/procedures/library`、`/procedures/drafts`、`/procedures/:id*`、`/maintenance/work-orders*`、`/maintenance/requests`、`/maintenance/preventive-maintenances`、`/maintenance/meters`、`/inventory/parts`、`/inventory/purchase-orders`、`/inventory/vendors`、`/analytics`、`/notifications`（路由保留，仅侧栏不再列）、`/billing/*`、`/`、`/login`、`/register`。

---

## Task 1: 路由前缀统一 + 旧路径重定向

**Files:**
- Modify: `frontend/src/router/index.ts`
- Test: `frontend/tests/unit/router/redirects.spec.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/router/redirects.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routes } from '@/router/routes'

// router/index.ts 须导出 routes 供测试复用（见 Step 3）。
function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

const REDIRECTS: Array<[string, string]> = [
  ['/folders', '/procedures/folders'],
  ['/maindata/assets', '/assets'],
  ['/maindata/locations', '/assets/locations'],
  ['/inventory/multi-parts', '/inventory/parts/kits'],
  ['/inventory/customers', '/maintenance/customers'],
  ['/platform/users', '/admin/users'],
  ['/platform/roles', '/admin/roles'],
  ['/platform/teams', '/admin/teams'],
  ['/platform/settings', '/admin/company'],
  ['/platform/currencies', '/admin/currencies'],
  ['/settings', '/admin/settings'],
  ['/settings/fields', '/admin/fields'],
  ['/settings/heading-rules', '/admin/heading-rules'],
  ['/audit-logs', '/admin/audit-logs'],
]

describe('router 旧路径重定向', () => {
  it.each(REDIRECTS)('%s 重定向到 %s', async (oldPath, newPath) => {
    const router = makeRouter()
    await router.push(oldPath)
    await router.isReady()
    expect(router.currentRoute.value.path).toBe(newPath)
  })

  const NEW_PATHS = [
    '/procedures/folders', '/assets', '/assets/locations',
    '/inventory/parts/kits', '/maintenance/customers',
    '/admin/users', '/admin/roles', '/admin/teams', '/admin/company',
    '/admin/currencies', '/admin/settings', '/admin/fields', '/admin/heading-rules',
    '/admin/audit-logs',
  ]
  it.each(NEW_PATHS)('新路径 %s 可解析到已命名路由', async (p) => {
    const router = makeRouter()
    await router.push(p)
    await router.isReady()
    expect(router.currentRoute.value.matched.length).toBeGreaterThan(0)
    expect(router.currentRoute.value.name).toBeTruthy()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npm run test -- tests/unit/router/redirects.spec.ts`
Expected: FAIL —— `@/router/routes` 不存在 / 旧路径仍解析到旧 path。

- [ ] **Step 3: 抽出 routes 并改写路径 + 重定向**

新建 `frontend/src/router/routes.ts`，把 `index.ts` 现有 `const routes: RouteRecordRaw[] = [...]` 整体迁入并 `export`。在迁移中按「路由变更总表」修改这 14 条记录的 `path`，并紧随每条新路由追加一条 `redirect` 记录指向新 path。示例（用户项）：

```ts
{
  path: '/admin/users',
  name: 'platform-users',
  component: () => import('@/views/platform/UsersView.vue'),
  meta: { title: '用户', requiresAuth: true, requiredPermission: 'user.view' },
},
{ path: '/platform/users', redirect: '/admin/users' },
```

对全部 14 项同样处理（`name` 与 `component` 保持不变，仅 `path` 改新值并加对应 redirect）。`/inventory/multi-parts` 的 redirect 目标为 `/inventory/parts/kits`（该新路由在 Task 2 落地 PartsHubView；本 Task 先加 redirect 记录，新路由的 component 暂指向现有 `MultiPartsView.vue` 以便测试通过，Task 2 再改为 PartsHubView 子路由）。

`index.ts` 改为从 `routes.ts` 导入：

```ts
import { createRouter, createWebHistory } from 'vue-router'
import { authGuard } from './guard'
import { routes } from './routes'

const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(authGuard)
export default router
```

`RouteMeta` 的 `declare module` 块保留在 `routes.ts` 顶部（随 routes 迁移）。

- [ ] **Step 4: 跑测试确认通过**

Run: `npm run test -- tests/unit/router/redirects.spec.ts`
Expected: PASS（28 用例：14 重定向 + 14 新路径可达）。

- [ ] **Step 5: typecheck**

Run: `npm run typecheck`
Expected: 无错误。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/router/index.ts frontend/src/router/routes.ts frontend/tests/unit/router/redirects.spec.ts
git commit -m "feat(router): 统一侧栏路由前缀 + 旧路径重定向"
```

---

## Task 2: PartsHubView —— 备件库存页内 Tab 下沉多备件套件

**Files:**
- Create: `frontend/src/views/inventory/PartsHubView.vue`
- Modify: `frontend/src/views/inventory/PartsView.vue`（加 `embedded` prop）
- Modify: `frontend/src/views/inventory/MultiPartsView.vue`（加 `embedded` prop）
- Modify: `frontend/src/router/routes.ts`（`/inventory/parts` 与 `/inventory/parts/kits` 指向 PartsHubView）
- Test: `frontend/tests/unit/views/PartsHubView.spec.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/views/PartsHubView.spec.ts`：

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import PartsHubView from '@/views/inventory/PartsHubView.vue'

// 子视图依赖大量 api；用 stub 隔离，只验 Hub 的 tab/路由编排。
vi.mock('@/views/inventory/PartsView.vue', () => ({
  default: { name: 'PartsView', props: ['embedded'], template: '<div class="stub-parts" />' },
}))
vi.mock('@/views/inventory/MultiPartsView.vue', () => ({
  default: { name: 'MultiPartsView', props: ['embedded'], template: '<div class="stub-kits" />' },
}))

function makeRouter(path: string): Router {
  return createRouter({
    history: createMemoryHistory(path),
    routes: [
      { path: '/inventory/parts', name: 'inventory-parts', component: PartsHubView },
      { path: '/inventory/parts/kits', name: 'inventory-multi-parts', component: PartsHubView },
    ],
  })
}

async function mountHub(path: string) {
  setActivePinia(createPinia())
  const router = makeRouter(path)
  await router.push(path)
  await router.isReady()
  return { w: mount(PartsHubView, { global: { plugins: [router] } }), router }
}

describe('PartsHubView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('两个 tab：备件库存 / 多备件套件', async () => {
    const { w } = await mountHub('/inventory/parts')
    expect(w.text()).toContain('备件库存')
    expect(w.text()).toContain('多备件套件')
  })

  it('/inventory/parts 激活备件 tab，渲染 PartsView(embedded)', async () => {
    const { w } = await mountHub('/inventory/parts')
    expect(w.find('.stub-parts').exists()).toBe(true)
  })

  it('/inventory/parts/kits 激活套件 tab，渲染 MultiPartsView(embedded)', async () => {
    const { w } = await mountHub('/inventory/parts/kits')
    expect(w.find('.stub-kits').exists()).toBe(true)
  })

  it('切到套件 tab 时 push 到 /inventory/parts/kits', async () => {
    const { w, router } = await mountHub('/inventory/parts')
    const kitsTab = w.findAll('.el-tabs__item').find((t) => t.text().includes('多备件套件'))!
    await kitsTab.trigger('click')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/inventory/parts/kits')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npm run test -- tests/unit/views/PartsHubView.spec.ts`
Expected: FAIL —— `PartsHubView.vue` 不存在。

- [ ] **Step 3: 创建 PartsHubView.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import PartsView from './PartsView.vue'
import MultiPartsView from './MultiPartsView.vue'

const route = useRoute()
const router = useRouter()

// tab 与路由双向绑定：/inventory/parts → parts，/inventory/parts/kits → kits。
const activeTab = computed<string>(() => (route.path.endsWith('/kits') ? 'kits' : 'parts'))

function onTabChange(name: string | number): void {
  const target = name === 'kits' ? '/inventory/parts/kits' : '/inventory/parts'
  if (route.path !== target) void router.push(target)
}
</script>

<template>
  <div class="page">
    <h2 class="page-title">备件库存</h2>
    <el-tabs :model-value="activeTab" @update:model-value="onTabChange">
      <el-tab-pane label="备件库存" name="parts">
        <PartsView v-if="activeTab === 'parts'" embedded />
      </el-tab-pane>
      <el-tab-pane label="多备件套件" name="kits">
        <MultiPartsView v-if="activeTab === 'kits'" embedded />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
```

- [ ] **Step 4: 给 PartsView/MultiPartsView 加 `embedded` prop**

在 `PartsView.vue` 的 `<script setup>` 加（紧随现有 imports 后）：

```ts
defineProps<{ embedded?: boolean }>()
```

模板顶层将 `<div class="page"><h2 class="page-title">备件库存</h2>` 改为去掉外层 `.page` 与标题（嵌入时由 Hub 提供）。最小改法：根节点保留 `.page`，标题加条件渲染——

```vue
<template>
  <div :class="embedded ? '' : 'page'">
    <h2 v-if="!embedded" class="page-title">备件库存</h2>
    <!-- 其余内容不变 -->
```

对 `MultiPartsView.vue` 同样处理（`defineProps<{ embedded?: boolean }>()` + 标题/外层条件）。确认 `MultiPartsView.vue` 现有顶层标题文案后改为 `v-if="!embedded"`。

- [ ] **Step 5: routes.ts 指向 PartsHubView**

把 `/inventory/parts` 路由 component 改为 PartsHubView，并新增 `/inventory/parts/kits` 命名路由（同 component）：

```ts
{
  path: '/inventory/parts',
  name: 'inventory-parts',
  component: () => import('@/views/inventory/PartsHubView.vue'),
  meta: { title: '备件库存', requiresAuth: true, requiredPermission: 'part.view' },
},
{
  path: '/inventory/parts/kits',
  name: 'inventory-multi-parts',
  component: () => import('@/views/inventory/PartsHubView.vue'),
  meta: { title: '多备件套件', requiresAuth: true, requiredPermission: 'part.view' },
},
```

删除 Task 1 中临时指向 `MultiPartsView.vue` 的 `/inventory/parts/kits` 记录（避免重复 name）。`/inventory/multi-parts` → `/inventory/parts/kits` 的 redirect 保留。

- [ ] **Step 6: 跑测试确认通过**

Run: `npm run test -- tests/unit/views/PartsHubView.spec.ts tests/unit/router/redirects.spec.ts`
Expected: PASS。同时跑 MultiPartsView 既有测试确认未破：
Run: `npm run test -- tests/unit/views/MultiPartsView.spec.ts`（按实际文件名）
Expected: PASS。

- [ ] **Step 7: typecheck + 提交**

```bash
npm run typecheck
git add frontend/src/views/inventory/PartsHubView.vue frontend/src/views/inventory/PartsView.vue frontend/src/views/inventory/MultiPartsView.vue frontend/src/router/routes.ts frontend/tests/unit/views/PartsHubView.spec.ts
git commit -m "feat(inventory): 备件库存页内 Tab 承载多备件套件（PartsHubView）"
```

---

## Task 3: AppSidebar 结构重构

**Files:**
- Modify: `frontend/src/components/AppSidebar.vue`
- Test: `frontend/tests/unit/AppSidebar.spec.ts`（重写断言）

- [ ] **Step 1: 改写 AppSidebar.spec.ts 断言到目标态**

更新 `makeRouter` 的 routes 为新前缀（`/assets`、`/assets/locations`、`/admin/*`、`/maintenance/customers`、`/inventory/parts/kits`，移除 `/maindata/*`、`/platform/*`、`/settings*`、`/folders`、`/audit-logs`、`/inventory/customers`、`/inventory/multi-parts`、`/notifications`）。改写关键用例：

```ts
it('collapsed=false：6 个 group-label（SOP/维护/资产/库存采购/分析/管理）', async () => {
  const w = await mountSidebar('/procedures/library')
  const labels = w.findAll('.menu-group-label')
  expect(labels.map((l) => l.text())).toEqual(['SOP', '维护', '资产', '库存采购', '分析', '管理'])
})

it('SOP 组含 程序库/草稿箱/文件夹（不再含审计日志）', async () => {
  const w = await mountSidebar('/procedures/library')
  expect(w.text()).toContain('程序库')
  expect(w.text()).toContain('文件夹')
})

it('通知中心已从侧栏移除（顶栏铃铛为唯一入口）', async () => {
  setUser('manager', ['analytics.view'])
  const w = await mountSidebar('/analytics')
  expect(w.text()).not.toContain('通知中心')
})

it('客户归入维护组', async () => {
  const w = await mountSidebar('/procedures/library')
  const items = w.findAll('.el-menu-item')
  expect(items.some((i) => i.text().includes('客户'))).toBe(true)
})

it('管理组：super_admin 见货币，非 super_admin 不见', async () => {
  setUser('super_admin')
  const w1 = await mountSidebar('/admin/users')
  expect(w1.text()).toContain('货币')
  setActivePinia(createPinia())
  setUser('manager')
  const w2 = await mountSidebar('/admin/users')
  expect(w2.text()).not.toContain('货币')
})

it.each([
  ['/assets', '/assets'],
  ['/assets/locations', '/assets/locations'],
  ['/admin/users', '/admin/users'],
  ['/admin/settings', '/admin/settings'],
  ['/admin/fields', '/admin/fields'],
  ['/admin/audit-logs', '/admin/audit-logs'],
  ['/maintenance/customers', '/maintenance/customers'],
  ['/inventory/parts/kits', '/inventory/parts'],
  ['/procedures/folders', '/procedures/folders'],
])('在 %s 时 activeMenu 为 %s', async (path, active) => {
  setUser('super_admin')
  const w = await mountSidebar(path)
  expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe(active)
})
```

保留并按需调整原有 SOP/维护/分析门控相关用例（`analytics.view`、`super_admin` 货币过滤逻辑沿用，仅断言文案/路径随新结构更新）。

- [ ] **Step 2: 跑测试确认失败**

Run: `npm run test -- tests/unit/AppSidebar.spec.ts`
Expected: FAIL（组标签数组不符、activeMenu 旧值、通知中心仍存在等）。

- [ ] **Step 3: 重写 AppSidebar.vue 数据模型 + 模板 + activeMenu**

`<script setup>` 中：扩展类型并重排 `groups`。

```ts
interface NavItem {
  label: string
  path?: string
  requiredPermission?: string
  feature?: string
  icon?: Component
}
interface NavSubGroup {
  label: string
  icon?: Component
  items: NavItem[]
}
type NavEntry = NavItem | NavSubGroup
interface NavGroup {
  label: string
  entries: NavEntry[]
}

function isSubGroup(e: NavEntry): e is NavSubGroup {
  return (e as NavSubGroup).items !== undefined
}
```

管理组的人员/组织/系统子分组项，货币按角色过滤（沿用原逻辑）：

```ts
const orgConfigItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [{ label: '公司设置', path: '/admin/company', icon: OfficeBuilding }]
  if (auth.user?.role_code === 'super_admin') {
    items.push({ label: '货币', path: '/admin/currencies', icon: Coin })
  }
  return items
})
```

分析组（去通知中心，仅 analytics.view 门控）：

```ts
const analyticsItems = computed<NavItem[]>(() => {
  if (auth.hasPermission('analytics.view')) {
    return [{
      label: '分析仪表盘', path: '/analytics',
      requiredPermission: 'analytics.view', feature: 'analytics', icon: DataAnalysis,
    }]
  }
  return []
})
```

`groups`：

```ts
const groups = computed<NavGroup[]>(() => [
  {
    label: 'SOP',
    entries: [
      { label: '程序库', path: '/procedures/library', feature: 'sop', icon: Document },
      { label: '草稿箱', path: '/procedures/drafts', feature: 'sop', icon: EditPen },
      { label: '文件夹', path: '/procedures/folders', feature: 'sop', icon: Folder },
    ],
  },
  {
    label: '维护',
    entries: [
      { label: '工单', path: '/maintenance/work-orders', icon: Tickets },
      { label: '请求', path: '/maintenance/requests', icon: ChatDotRound },
      { label: '预防性维护', path: '/maintenance/preventive-maintenances', feature: 'preventive_maintenance', icon: Timer },
      { label: '计量', path: '/maintenance/meters', feature: 'meters', icon: Odometer },
      { label: '客户', path: '/maintenance/customers', icon: Avatar },
    ],
  },
  {
    label: '资产',
    entries: [
      { label: '资产', path: '/assets', icon: Box },
      { label: '位置', path: '/assets/locations', icon: Location },
    ],
  },
  {
    label: '库存采购',
    entries: [
      { label: '备件库存', path: '/inventory/parts', icon: Goods },
      { label: '采购单', path: '/inventory/purchase-orders', feature: 'purchasing', icon: ShoppingCart },
      { label: '供应商', path: '/inventory/vendors', icon: Shop },
    ],
  },
  {
    label: '分析',
    entries: analyticsItems.value,
  },
  {
    label: '管理',
    entries: [
      { label: '人员与权限', icon: User, items: [
        { label: '用户', path: '/admin/users', icon: User },
        { label: '角色', path: '/admin/roles', icon: UserFilled },
        { label: '团队', path: '/admin/teams', icon: Connection },
      ] },
      { label: '组织配置', icon: OfficeBuilding, items: orgConfigItems.value },
      { label: '系统配置', icon: Setting, items: [
        { label: '系统设置', path: '/admin/settings', icon: Setting },
        { label: '字段管理', path: '/admin/fields', icon: Grid },
        { label: '标题字典', path: '/admin/heading-rules', icon: Collection },
      ] },
      { label: '审计', icon: List, items: [
        { label: '审计日志', path: '/admin/audit-logs', icon: List },
      ] },
    ],
  },
])
```

`activeMenu` 重写：

```ts
const activeMenu = computed<string>(() => {
  const p = route.path
  if (p.startsWith('/admin/')) return p
  if (p.startsWith('/assets/locations')) return '/assets/locations'
  if (p.startsWith('/assets')) return '/assets'
  if (p.startsWith('/inventory/parts')) return '/inventory/parts'
  if (p.startsWith('/inventory/')) return p
  if (p.startsWith('/maintenance/work-orders')) return '/maintenance/work-orders'
  if (p.startsWith('/maintenance/')) return p
  if (p.startsWith('/analytics')) return '/analytics'
  if (p.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (p.startsWith('/procedures/folders')) return '/procedures/folders'
  if (p.startsWith('/procedures')) return '/procedures/library'
  return ''
})
```

移除 `Bell` import（通知中心去除）。`defineExpose` 改为 `{ activeMenu, groups }`（移除 `platformItems`/`insightItems`，相应 spec 用例改读 `groups` 或 DOM 文案——Step 1 已按 DOM 文案断言）。

模板支持 `el-sub-menu`：

```vue
<template v-for="g in groups" :key="g.label">
  <div v-if="!collapsed && g.entries.length" class="menu-group-label">{{ g.label }}</div>
  <template v-for="entry in g.entries" :key="entry.label">
    <el-sub-menu v-if="isSubGroup(entry)" :index="`grp:${entry.label}`">
      <template #title>
        <el-icon v-if="entry.icon" class="nav-icon"><component :is="entry.icon" /></el-icon>
        <span>{{ entry.label }}</span>
      </template>
      <el-menu-item v-for="it in entry.items" :key="it.label" :index="menuIndex(it)">
        <el-icon v-if="it.icon" class="nav-icon"><component :is="it.icon" /></el-icon>
        <template #title>
          {{ it.label }}
          <el-icon v-if="isLocked(it)" class="lock-icon"><Lock /></el-icon>
        </template>
      </el-menu-item>
    </el-sub-menu>
    <el-menu-item v-else :index="menuIndex(entry)">
      <el-icon v-if="entry.icon" class="nav-icon"><component :is="entry.icon" /></el-icon>
      <template #title>
        {{ entry.label }}
        <el-icon v-if="isLocked(entry)" class="lock-icon"><Lock /></el-icon>
      </template>
    </el-menu-item>
  </template>
</template>
```

> 注：移除了原 `soon`/`即将上线` 分支（现无 soon 项；如 grep 仍有引用则一并清理）。`NavItem.soon` 字段及 `:disabled="it.soon"` 一并删除。

- [ ] **Step 4: 子菜单选中态样式**

现有 `.is-active::before` 竖条规则对 `el-sub-menu` 内 `el-menu-item.is-active` 同样生效（选择器 `.app-aside :deep(.el-menu-item.is-active)` 已覆盖嵌套项）。补一条：sub-menu 标题在其子项激活时的高亮不必额外处理（EP 默认给 `.el-sub-menu.is-active > .el-sub-menu__title` 上色，走 `--el-menu-active-color`）。无需新增 CSS；如 dev 实测发现竖条偏移（sub-menu 内项有额外左 padding），在 Task 5 微调 `:deep(.el-sub-menu .el-menu-item.is-active)::before { left: 0 }`。

- [ ] **Step 5: 跑测试确认通过**

Run: `npm run test -- tests/unit/AppSidebar.spec.ts`
Expected: PASS。

- [ ] **Step 6: typecheck + lint + 提交**

```bash
npm run typecheck && npm run lint
git add frontend/src/components/AppSidebar.vue frontend/tests/unit/AppSidebar.spec.ts
git commit -m "feat(sidebar): 重排分组/命名 + 管理组折叠子菜单 + 移除通知中心"
```

---

## Task 4: AppTopBar 命令面板路径更新

**Files:**
- Modify: `frontend/src/components/AppTopBar.vue`
- Test: `frontend/tests/unit/AppTopBar.spec.ts`

- [ ] **Step 1: 改 spec 断言到新路径**

`AppTopBar.spec.ts` 对 `MENU_COMMANDS` 做契约断言。更新为：

```ts
expect(wrapper.vm.MENU_COMMANDS).toEqual([
  { group: '配置', label: '文件夹配置', path: '/procedures/folders' },
  { group: '配置', label: '系统设置', path: '/admin/settings' },
  { group: '配置', label: '字段管理', path: '/admin/fields' },
  { group: '配置', label: '标题字典', path: '/admin/heading-rules' },
  { group: '历史', label: '审计日志', path: '/admin/audit-logs' },
])
```

（按 spec 现有断言写法对齐；若它逐项断言 path，则逐项改对应新值。）

- [ ] **Step 2: 跑测试确认失败**

Run: `npm run test -- tests/unit/AppTopBar.spec.ts`
Expected: FAIL（path 仍为旧值）。

- [ ] **Step 3: 改 AppTopBar.vue 的 MENU_COMMANDS**

```ts
const MENU_COMMANDS: readonly MenuCommand[] = [
  { group: '配置', label: '文件夹配置', path: '/procedures/folders' },
  { group: '配置', label: '系统设置', path: '/admin/settings' },
  { group: '配置', label: '字段管理', path: '/admin/fields' },
  { group: '配置', label: '标题字典', path: '/admin/heading-rules' },
  { group: '历史', label: '审计日志', path: '/admin/audit-logs' },
]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npm run test -- tests/unit/AppTopBar.spec.ts`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/AppTopBar.vue frontend/tests/unit/AppTopBar.spec.ts
git commit -m "feat(topbar): 命令面板导航路径对齐新前缀"
```

---

## Task 5: 全量验证 + dev 暗色实测

**Files:** 无新增（验证 + 必要微调）

- [ ] **Step 1: 全量单测**

Run: `npm run test`
Expected: 全绿，文件/用例数 ≥ 基线（826 + 新增 redirects/PartsHub 用例，扣除被合并/删除的旧用例）。任何红用例修复后重跑。

- [ ] **Step 2: typecheck + lint**

Run: `npm run typecheck && npm run lint`
Expected: 无错误、无警告（lint `--max-warnings 0`）。

- [ ] **Step 3: dev 实测（参照 running-smartsop-dev skill）**

启动后端 8000 + 前端 5173，登录后用 chrome-devtools 在**暗色**下逐项核对：
- 侧栏 6 组顺序：SOP / 维护 / 资产 / 库存采购 / 分析 / 管理。
- 「管理」组 4 个子菜单可展开/折叠；展开后子项可点；选中项左侧陶土橙竖条对齐、无错位。
- 侧栏折叠态（collapsed）下管理组子菜单图标显示且 hover 弹出子项。
- 导航：资产→`/assets`、位置→`/assets/locations`、客户→`/maintenance/customers`、各 `/admin/*` 均正常加载页面。
- 备件库存页两 Tab 切换：`/inventory/parts` ↔ `/inventory/parts/kits`，URL 同步、刷新保持、无双重标题。
- 旧链接 redirect：手输 `/platform/users`、`/maindata/assets`、`/settings/fields`、`/inventory/customers`、`/folders` 均跳到新路径。
- 通知：侧栏无「通知中心」，顶栏铃铛仍可打开并「查看全部」跳 `/notifications`。
- 顶栏命令面板「配置/历史」各项跳转到新路径。

截图留档（参照 multipart dev 视觉冒烟惯例）。

- [ ] **Step 4: 收尾提交（如有微调）**

```bash
git add -A
git commit -m "test(sidebar): dev 暗色冒烟 + 子菜单选中态微调"
```

---

## 完成标准

- `npm run test` / `typecheck` / `lint` 全绿。
- 侧栏 6 组按新结构与命名渲染；管理组折叠正常；通知中心仅存于顶栏。
- 14 条旧路径全部 redirect 到新路径；新路径直达。
- 备件库存页 Tab 承载多备件套件，URL 路由驱动。
- dev 暗色实测各项通过并截图留档。

## Self-Review 记录

- **Spec 覆盖**：第 2 节结构 → Task 3；第 3 节路由表 → Task 1（+Task 2 的 parts/kits）；§4.1 AppSidebar → Task 3；§4.2 router → Task 1；§4.3 PartsView → Task 2；§4.4 内链(AppTopBar) → Task 4，内链(测试) → 各 Task；§5 验证 → Task 5；决策 1（通知移除）→ Task 3；决策 2（Tab）→ Task 2；决策 3（客户入维护）→ Task 1+3；决策 4（路由+重定向）→ Task 1；决策 5（管理组折叠）→ Task 3。无遗漏。
- **类型一致**：`NavItem`/`NavSubGroup`/`NavEntry`/`isSubGroup` 在 Task 3 定义并使用一致；`routes`（Task 1 导出）被 redirects.spec 与 index.ts 共用；`embedded` prop 在 Task 2 三处一致。
- **占位符**：无 TBD/TODO；所有代码步骤含完整代码。
- **风险点**：AppTopBar.spec.ts 与 MultiPartsView.spec.ts 的精确断言写法需执行时按文件实际内容对齐（计划已标注「按 spec 现有写法对齐」）。
