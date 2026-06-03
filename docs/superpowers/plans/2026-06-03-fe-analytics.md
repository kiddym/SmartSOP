# FE-6 分析仪表盘 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 单页分析仪表盘——把 7 个已就绪的 `/api/v1/analytics/*` 聚合端点变成可用的可视化界面（工单/成本/资产可靠性/库存/请求/人员/趋势 + CSV 导出）。

**Architecture:** Vue 3 `<script setup lang="ts">` + Element Plus + echarts/vue-echarts（按需注册）。单路由 `/analytics` → `AnalyticsView` 壳（全局过滤栏 + `el-tabs` 七 lazy 面板），每面板独立组件消费自身端点，图表统一经 `BaseChart` 渲染（测试 mock 缝）。**纯前端，无后端改动、无迁移。**

**Tech Stack:** Vite + TS + Element Plus + echarts + vue-echarts + Pinia + vue-router + vitest。门禁：`npm run typecheck`（vue-tsc）+ `npm run lint`（eslint --max-warnings 0）+ prettier + `npm run test`（vitest）。

**全局约定（每任务适用）：**
- 工作目录 `frontend/`；命令 `npm run ...`。分支 `feat/fe-analytics`（基于 main，spec 已提交）。
- 每任务：写测试 → 跑红 → 实现 → `npm run test` + `typecheck` + `lint` 绿 → prettier → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 仅中文、不做 i18n。RBAC：`const auth = useAuthStore()`；门控 `analytics.view`。
- 精确 `git add`，**勿纳入**仓库根未跟踪产物（`.claude/scheduled_tasks.lock`、`.verify-screenshots/*.png`）。
- 净室原创：复刻功能，绝不出现 "Atlas" 字样或复制其代码/文案。

**既有模式参考：**
- api：`src/api/locations.ts`（`http.get<T>(path).then(r=>r.data)`；http 是 axios 实例，baseURL 含 `/api/v1`）。
- view：`src/views/inventory/PurchaseOrdersView.vue`、`src/views/maintenance/RequestsView.vue`（state 分区 + helper 函数化映射 + scoped `.page/.page-title/.toolbar` + RBAC v-if）。
- 测试：`tests/unit/PurchaseOrdersView.spec.ts`（可变 auth mock + `mount(...,{global:{plugins:[ElementPlus]},attachTo:document.body})` + flushPromises + `afterEach(()=>{document.body.innerHTML=''})`）。
- 导航：`src/components/AppSidebar.vue`（`groups` computed；「洞察」组「分析仪表盘」现 `soon: true`；`activeMenu` 多 `if startsWith` 串联）。
- 路由：`src/router/index.ts`（扁平 + `meta.requiresAuth` + `requiredPermission`）。已有前缀 platform/maindata/inventory/maintenance；本计划新增 `/analytics`。
- 复用 api：`listAssetsMini`（`@/api/assets`，`AssetMini[]` 有 name）、`listLocationsMini`（`@/api/locations`，`LocationMini[]` 有 name）、`listUsers`（`@/api/users`，`UserRead[]` 有 name）、`listPartCategories`（`@/api/partCategories`，`PartCategoryRead[]` 有 name）、`listAssetCategories`（`@/api/assetCategories`，`AssetCategoryRead[]` 有 name）。
- 工具：`src/utils/format.ts` 的 `formatDate`。

**后端契约（已核实，types 以此为准；Decimal→`string`、float→`number`、int→`number`、date→`string`；baseURL 含 `/api/v1`）：**
- 端点全 GET、前缀 `/analytics`、门控 `analytics.view`：
  - `/work-orders`（`date_from`/`date_to`/`asset_id`/`location_id`）→ `WorkOrderAnalytics`
  - `/costs`（同上）→ `CostAnalytics`
  - `/asset-reliability`（+`category_id` 资产分类）→ `AssetReliabilityAnalytics`
  - `/inventory`（`date_from`/`date_to`/`category_id` 备件分类）→ `InventoryAnalytics`
  - `/requests`（`date_from`/`date_to`/`asset_id`/`location_id`）→ `RequestAnalytics`
  - `/personnel`（`date_from`/`date_to`）→ `PersonnelAnalytics`
  - `/trends`（`date_from`/`date_to`/`granularity`='day'|'week'）→ `TrendAnalytics`
  - `/{dashboard}/export`（同各面板参数）→ `text/csv` blob
- 工单状态枚举：`OPEN/IN_PROGRESS/ON_HOLD/COMPLETE/CANCELED`；优先级 `NONE/LOW/MEDIUM/HIGH`；请求状态 `PENDING/APPROVED/REJECTED/CANCELED`。

---

## Task 1: 依赖 + 骨架（echarts 接入 + BaseChart/KpiCard + types + api + 路由 + 导航 + AnalyticsView 壳）

**Files:**
- Modify: `package.json`（新增 echarts/vue-echarts）
- Create: `src/types/analytics.ts`
- Create: `src/api/analytics.ts`
- Create: `src/components/analytics/BaseChart.vue`、`src/components/analytics/KpiCard.vue`
- Create: `src/views/analytics/AnalyticsView.vue`、`src/views/analytics/panels/{WorkOrders,Costs,AssetReliability,Inventory,Requests,Personnel,Trends}Panel.vue`（占位骨架）
- Modify: `src/router/index.ts`、`src/components/AppSidebar.vue`
- Test: `tests/unit/analyticsApi.spec.ts`、`tests/unit/KpiCard.spec.ts`、`tests/unit/BaseChart.spec.ts`、`tests/unit/AppSidebar.spec.ts`（追加）

- [ ] **Step 1: 安装依赖**

Run: `cd frontend && npm install echarts vue-echarts`
Expected: package.json `dependencies` 出现 `echarts` 与 `vue-echarts`；`package-lock.json` 更新。

- [ ] **Step 2: 写失败测试 `tests/unit/analyticsApi.spec.ts`**

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ http: { get } }))

import {
  getWorkOrderAnalytics,
  getCostAnalytics,
  getAssetReliabilityAnalytics,
  getInventoryAnalytics,
  getRequestAnalytics,
  getPersonnelAnalytics,
  getTrendAnalytics,
  exportAnalytics,
} from '@/api/analytics'

describe('analytics api', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: {} })
  })

  it('getWorkOrderAnalytics GET /analytics/work-orders', async () => {
    await getWorkOrderAnalytics({ date_from: '2026-01-01', date_to: '2026-03-31' })
    expect(get).toHaveBeenCalledWith('/analytics/work-orders', {
      params: { date_from: '2026-01-01', date_to: '2026-03-31' },
    })
  })
  it('getCostAnalytics GET /analytics/costs', async () => {
    await getCostAnalytics({ asset_id: 'a1' })
    expect(get).toHaveBeenCalledWith('/analytics/costs', { params: { asset_id: 'a1' } })
  })
  it('getAssetReliabilityAnalytics GET /analytics/asset-reliability', async () => {
    await getAssetReliabilityAnalytics({ category_id: 'c1' })
    expect(get).toHaveBeenCalledWith('/analytics/asset-reliability', { params: { category_id: 'c1' } })
  })
  it('getInventoryAnalytics GET /analytics/inventory', async () => {
    await getInventoryAnalytics({ category_id: 'pc1' })
    expect(get).toHaveBeenCalledWith('/analytics/inventory', { params: { category_id: 'pc1' } })
  })
  it('getRequestAnalytics GET /analytics/requests', async () => {
    await getRequestAnalytics({})
    expect(get).toHaveBeenCalledWith('/analytics/requests', { params: {} })
  })
  it('getPersonnelAnalytics GET /analytics/personnel', async () => {
    await getPersonnelAnalytics({ date_from: '2026-01-01' })
    expect(get).toHaveBeenCalledWith('/analytics/personnel', { params: { date_from: '2026-01-01' } })
  })
  it('getTrendAnalytics GET /analytics/trends', async () => {
    await getTrendAnalytics({ granularity: 'week' })
    expect(get).toHaveBeenCalledWith('/analytics/trends', { params: { granularity: 'week' } })
  })

  it('exportAnalytics GET /analytics/{dashboard}/export blob', async () => {
    const blob = new Blob(['x'], { type: 'text/csv' })
    get.mockResolvedValueOnce({ data: blob })
    // jsdom 提供 URL.createObjectURL? 需 stub
    const createSpy = vi.fn().mockReturnValue('blob:x')
    const revokeSpy = vi.fn()
    // @ts-expect-error stub
    URL.createObjectURL = createSpy
    // @ts-expect-error stub
    URL.revokeObjectURL = revokeSpy
    await exportAnalytics('work-orders', { date_from: '2026-01-01' })
    expect(get).toHaveBeenCalledWith('/analytics/work-orders/export', {
      params: { date_from: '2026-01-01' },
      responseType: 'blob',
    })
    expect(createSpy).toHaveBeenCalled()
  })
})
```

- [ ] **Step 3: 跑红** `npm run test -- analyticsApi` → FAIL（模块不存在）。

- [ ] **Step 4: types `src/types/analytics.ts`**

```typescript
export interface AnalyticsParams {
  date_from?: string
  date_to?: string
  asset_id?: string
  location_id?: string
  category_id?: string
  granularity?: 'day' | 'week'
}

export interface CountRow {
  asset_id: string | null
  user_id: string | null
  category_id: string | null
  count: number
}

export interface WorkOrderAnalytics {
  date_from: string
  date_to: string
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  completed: number
  completion_rate: number
  overdue: number
  avg_cycle_time_hours: number | null
  avg_response_time_hours: number | null
  by_asset: CountRow[]
  by_user: CountRow[]
  by_category: CountRow[]
}

export interface RequestAnalytics {
  date_from: string
  date_to: string
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  received: number
  resolved: number
  converted: number
  avg_resolution_cycle_hours: number | null
}

export interface PartCostRow {
  part_id: string
  custom_id: string
  name: string
  qty: string
  cost: string
}
export interface AssetCostRow {
  asset_id: string | null
  cost: string
}
export interface VendorSpendRow {
  vendor_id: string
  spend: string
}
export interface MaintenanceCostByAssetRow {
  asset_id: string | null
  parts_cost: string
  labor_cost: string
  additional_cost: string
  total: string
}
export interface CostAnalytics {
  date_from: string
  date_to: string
  parts_consumption_cost: string
  consumption_by_part: PartCostRow[]
  consumption_by_asset: AssetCostRow[]
  po_spend_approved: string
  po_spend_by_vendor: VendorSpendRow[]
  labor_cost: string
  additional_cost: string
  total_maintenance_cost: string
  maintenance_cost_by_asset: MaintenanceCostByAssetRow[]
}

export interface AssetReliabilityRow {
  asset_id: string
  custom_id: string
  name: string
  availability_pct: number
  downtime_count: number
  total_downtime_hours: number
  mttr_hours: number | null
  mtbf_hours: number | null
  total_maintenance_cost: string
  acquisition_cost: string | null
  cost_to_value_ratio: number | null
}
export interface AssetReliabilityAnalytics {
  date_from: string
  date_to: string
  window_hours: number
  assets: AssetReliabilityRow[]
  fleet_availability_pct: number | null
  fleet_total_downtime_hours: number
  fleet_mttr_hours: number | null
  fleet_mtbf_hours: number | null
  fleet_total_maintenance_cost: string
}

export interface CategoryValueRow {
  category_id: string | null
  name: string | null
  value: string
}
export interface LowStockRow {
  part_id: string
  custom_id: string
  name: string
  quantity: string
  min_quantity: string
  shortfall: string
}
export interface TopConsumedRow {
  part_id: string
  custom_id: string
  name: string
  qty: string
}
export interface ABCRow {
  part_id: string
  custom_id: string
  name: string
  consumption_value: string
  cumulative_pct: number
  abc_class: string
}
export interface InventoryAnalytics {
  total_inventory_value: string
  inventory_value_by_category: CategoryValueRow[]
  low_stock_count: number
  low_stock_items: LowStockRow[]
  top_consumed_parts: TopConsumedRow[]
  abc_classification: ABCRow[]
  abc_summary: Record<string, number>
}

export interface PersonnelRow {
  user_id: string
  name: string | null
  created_count: number
  completed_count: number
  assigned_count: number
  labor_hours: number
  labor_cost: string
}
export interface PersonnelAnalytics {
  date_from: string
  date_to: string
  users: PersonnelRow[]
}

export interface TrendBucket {
  bucket_start: string
  work_orders_created: number
  work_orders_completed: number
  requests_received: number
  requests_resolved: number
}
export interface TrendAnalytics {
  date_from: string
  date_to: string
  granularity: string
  buckets: TrendBucket[]
}
```

- [ ] **Step 5: api `src/api/analytics.ts`**

```typescript
import { http } from './http'
import type {
  AnalyticsParams,
  WorkOrderAnalytics,
  CostAnalytics,
  AssetReliabilityAnalytics,
  InventoryAnalytics,
  RequestAnalytics,
  PersonnelAnalytics,
  TrendAnalytics,
} from '@/types/analytics'

export const getWorkOrderAnalytics = (params: AnalyticsParams = {}) =>
  http.get<WorkOrderAnalytics>('/analytics/work-orders', { params }).then((r) => r.data)
export const getCostAnalytics = (params: AnalyticsParams = {}) =>
  http.get<CostAnalytics>('/analytics/costs', { params }).then((r) => r.data)
export const getAssetReliabilityAnalytics = (params: AnalyticsParams = {}) =>
  http.get<AssetReliabilityAnalytics>('/analytics/asset-reliability', { params }).then((r) => r.data)
export const getInventoryAnalytics = (params: AnalyticsParams = {}) =>
  http.get<InventoryAnalytics>('/analytics/inventory', { params }).then((r) => r.data)
export const getRequestAnalytics = (params: AnalyticsParams = {}) =>
  http.get<RequestAnalytics>('/analytics/requests', { params }).then((r) => r.data)
export const getPersonnelAnalytics = (params: AnalyticsParams = {}) =>
  http.get<PersonnelAnalytics>('/analytics/personnel', { params }).then((r) => r.data)
export const getTrendAnalytics = (params: AnalyticsParams = {}) =>
  http.get<TrendAnalytics>('/analytics/trends', { params }).then((r) => r.data)

export const exportAnalytics = async (dashboard: string, params: AnalyticsParams = {}) => {
  const res = await http.get(`/analytics/${dashboard}/export`, { params, responseType: 'blob' })
  const url = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${dashboard}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 6: `src/components/analytics/BaseChart.vue`**

```vue
<script setup lang="ts">
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
])

defineProps<{ option: EChartsOption; height?: string }>()
</script>

<template>
  <VChart class="chart" :option="option" autoresize :style="{ height: height ?? '320px' }" />
</template>

<style scoped>
.chart {
  width: 100%;
}
</style>
```

- [ ] **Step 7: `src/components/analytics/KpiCard.vue`**

```vue
<script setup lang="ts">
defineProps<{ label: string; value: string | number; unit?: string; hint?: string }>()
</script>

<template>
  <el-card class="kpi" shadow="never">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value">{{ value }}<span v-if="unit" class="kpi-unit">{{ unit }}</span></div>
    <div v-if="hint" class="kpi-hint">{{ hint }}</div>
  </el-card>
</template>

<style scoped>
.kpi-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.kpi-value {
  font-size: 24px;
  font-weight: 600;
  margin-top: 4px;
}
.kpi-unit {
  font-size: 13px;
  font-weight: 400;
  margin-left: 4px;
  color: var(--el-text-color-secondary);
}
.kpi-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
```

- [ ] **Step 8: `tests/unit/KpiCard.spec.ts` 与 `tests/unit/BaseChart.spec.ts`**

`tests/unit/KpiCard.spec.ts`：
```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import KpiCard from '@/components/analytics/KpiCard.vue'

describe('KpiCard', () => {
  it('渲染 label/value/unit/hint', () => {
    const w = mount(KpiCard, {
      props: { label: '完成率', value: '85.0', unit: '%', hint: '近90天' },
      global: { plugins: [ElementPlus] },
    })
    expect(w.text()).toContain('完成率')
    expect(w.text()).toContain('85.0')
    expect(w.text()).toContain('%')
    expect(w.text()).toContain('近90天')
  })
})
```

`tests/unit/BaseChart.spec.ts`（mock vue-echarts 避免 jsdom canvas）：
```typescript
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="v-chart-stub" />' },
}))

import BaseChart from '@/components/analytics/BaseChart.vue'

describe('BaseChart', () => {
  it('挂载并接收 option 不报错', () => {
    const w = mount(BaseChart, { props: { option: { series: [] } } })
    expect(w.find('.v-chart-stub').exists()).toBe(true)
  })
})
```

- [ ] **Step 9: 占位面板视图（7 个）**

`src/views/analytics/panels/WorkOrdersPanel.vue`（其余六个同结构，标题文案分别「成本」「资产可靠性」「库存」「请求」「人员」「趋势」，文件名见 Files）：
```vue
<script setup lang="ts">
defineProps<{ baseParams: Record<string, string | undefined> }>()
</script>
<template><div class="panel">工单</div></template>
```

- [ ] **Step 10: `src/views/analytics/AnalyticsView.vue` 壳**

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import type { AssetMini, LocationMini } from '@/types/maindata'
import WorkOrdersPanel from './panels/WorkOrdersPanel.vue'
import CostsPanel from './panels/CostsPanel.vue'
import AssetReliabilityPanel from './panels/AssetReliabilityPanel.vue'
import InventoryPanel from './panels/InventoryPanel.vue'
import RequestsPanel from './panels/RequestsPanel.vue'
import PersonnelPanel from './panels/PersonnelPanel.vue'
import TrendsPanel from './panels/TrendsPanel.vue'

function defaultRange(): [string, string] {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 90)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return [fmt(from), fmt(to)]
}

const dateRange = ref<[string, string] | null>(defaultRange())
const assetId = ref('')
const locationId = ref('')
const activeTab = ref('work-orders')
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])

const baseParams = computed<Record<string, string | undefined>>(() => ({
  date_from: dateRange.value?.[0],
  date_to: dateRange.value?.[1],
  asset_id: assetId.value || undefined,
  location_id: locationId.value || undefined,
}))

onMounted(async () => {
  assetsMini.value = await listAssetsMini()
  locationsMini.value = await listLocationsMini()
})
</script>

<template>
  <div class="page">
    <div class="page-title">分析仪表盘</div>
    <div class="toolbar">
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
      />
      <el-select v-model="assetId" clearable filterable placeholder="资产" style="width: 180px">
        <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-select v-model="locationId" clearable filterable placeholder="位置" style="width: 180px">
        <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
      </el-select>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="工单" name="work-orders" lazy>
        <WorkOrdersPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="成本" name="costs" lazy>
        <CostsPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="资产可靠性" name="asset-reliability" lazy>
        <AssetReliabilityPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="库存" name="inventory" lazy>
        <InventoryPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="请求" name="requests" lazy>
        <RequestsPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="人员" name="personnel" lazy>
        <PersonnelPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="趋势" name="trends" lazy>
        <TrendsPanel :base-params="baseParams" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.page {
  padding: 16px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 12px;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
</style>
```
> 先 Read `src/views/inventory/PurchaseOrdersView.vue` 确认 `.page/.page-title/.toolbar` 样式与既有一致；若既有有公共样式约定则对齐。`AssetMini`/`LocationMini` 在 `@/types/maindata`（参 RequestsView 的 import）。

- [ ] **Step 11: 路由 `src/router/index.ts` 加 1 条**

先 Read 现有 `/maintenance/*` 路由块，仿照加入：
```typescript
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('@/views/analytics/AnalyticsView.vue'),
    meta: { title: '分析仪表盘', requiresAuth: true, requiredPermission: 'analytics.view' },
  },
```

- [ ] **Step 12: 导航 `src/components/AppSidebar.vue`**

先 Read。「洞察」组「分析仪表盘」项改为带 path + 门控（去 `soon`）：
```typescript
      { label: '分析仪表盘', path: '/analytics', requiredPermission: 'analytics.view' },
```
> 若 sidebar 项类型无 `requiredPermission` 字段或门控走别的机制（如渲染时 `auth.hasPermission`），按该文件既有写法适配；至少保证：有 `analytics.view` 权限才显示且可点、无 soon。「通知中心」仍 soon。
`activeMenu` computed 增加：`if (route.path.startsWith('/analytics')) return route.path`（或 `'/analytics'`，按既有写法）。

`tests/unit/AppSidebar.spec.ts`：先 Read 现有结构，追加断言——「洞察」组「分析仪表盘」有 `path`、无 `soon`（有 analytics.view 权限时）。既有断言不破。

- [ ] **Step 13: 跑绿 + 门禁**

Run: `cd frontend && npm run test && npm run typecheck && npm run lint`
Expected: PASS / 0 errors / 0 warnings。
prettier：`npx prettier --write "src/types/analytics.ts" "src/api/analytics.ts" "src/components/analytics/*.vue" "src/views/analytics/**/*.vue" "tests/unit/analyticsApi.spec.ts" "tests/unit/KpiCard.spec.ts" "tests/unit/BaseChart.spec.ts" "src/router/index.ts" "src/components/AppSidebar.vue" "tests/unit/AppSidebar.spec.ts"`

- [ ] **Step 14: commit**

```bash
git add package.json package-lock.json src/types/analytics.ts src/api/analytics.ts src/components/analytics/ src/views/analytics/ src/router/index.ts src/components/AppSidebar.vue tests/unit/analyticsApi.spec.ts tests/unit/KpiCard.spec.ts tests/unit/BaseChart.spec.ts tests/unit/AppSidebar.spec.ts
git commit -m "feat(fe-analytics): echarts deps + BaseChart/KpiCard + analytics api/types + route + sidebar + shell

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 面板任务通用约定（T2–T8 适用）

每个面板组件 `<script setup lang="ts">`：
- props `baseParams: Record<string, string | undefined>`。
- state：自身响应数据 `ref<XxxAnalytics | null>(null)`、`loading`、（部分）`assetsMini`/`users` 做 id→name 映射、（部分）自身分类过滤。
- `buildParams()`：从 `props.baseParams` 拷贝并剔除 `undefined` 键（`Object.fromEntries(Object.entries(props.baseParams).filter(([, v]) => v !== undefined))`），叠加面板特有键（category_id/granularity）。**注意**：personnel/trends 端点只认 date_*，多余键后端忽略无害，但为干净起见 personnel/trends 面板可只取 date_from/date_to。
- `fetch()`：`loading=true; try { data.value = await getXxxAnalytics(buildParams()) } catch { ElMessage.error('加载失败，请重试') } finally { loading=false }`。
- `watch(() => props.baseParams, fetch, { immediate: true, deep: true })`。
- 图表经 `<BaseChart :option="xxxOption" />`，option 用 `computed` 从 data 生成（data 为 null 时返回空 series 的安全 option）。
- 「导出CSV」按钮 `@click="exportAnalytics('<dashboard>', buildParams())"`。
- helper 函数化映射：`assetName(id)`/`userName(id)` 查 mini（缺失→id 或 '—'）。
- 模板根 `<div class="panel" v-loading="loading">`，KPI 行 `el-row`/`el-col`，图表/表格分块。
- 数值展示：`pct(n)`=`(n).toFixed(1)`、`hrs(n)`=`n==null?'—':n.toFixed(1)`、金额 string 直接渲染（null→'—'）。

每个面板 spec 通用骨架（mock api + BaseChart + auth）：
```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: { name: 'BaseChart', props: ['option', 'height'], template: '<div class="chart-stub" />' },
}))
// 其余 mock 见各任务
```
> 关键：面板测试**必 mock `@/components/analytics/BaseChart.vue`** 为 stub（避免 echarts/jsdom canvas）。断言聚焦 KPI 文本、表格行、api 调用参数、导出触发、空数据兜底。用 `attachTo: document.body` + `afterEach` 清 DOM。

---

## Task 2: 工单面板 WorkOrdersPanel

**Files:** Create `src/views/analytics/panels/WorkOrdersPanel.vue`（覆盖占位）；Test `tests/unit/WorkOrdersPanel.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/WorkOrdersPanel.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: { name: 'BaseChart', props: ['option', 'height'], template: '<div class="chart-stub" />' },
}))
const { gwo, exp } = vi.hoisted(() => ({ gwo: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getWorkOrderAnalytics: gwo, exportAnalytics: exp }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]) }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]) }))

import WorkOrdersPanel from '@/views/analytics/panels/WorkOrdersPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  total: 42,
  by_status: { OPEN: 10, IN_PROGRESS: 5, COMPLETE: 25, ON_HOLD: 1, CANCELED: 1 },
  by_priority: { HIGH: 8, MEDIUM: 20, LOW: 10, NONE: 4 },
  completed: 25,
  completion_rate: 0.595,
  overdue: 3,
  avg_cycle_time_hours: 48.5,
  avg_response_time_hours: 6.2,
  by_asset: [{ asset_id: 'a1', user_id: null, category_id: null, count: 12 }],
  by_user: [{ asset_id: null, user_id: 'u1', category_id: null, count: 15 }],
  by_category: [],
}

function mountPanel(params = { date_from: '2026-01-01', date_to: '2026-03-31' }) {
  return mount(WorkOrdersPanel, {
    props: { baseParams: params },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gwo.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrdersPanel', () => {
  it('加载并渲染 KPI（总数/逾期）', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gwo).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31' })
    expect(w.text()).toContain('42') // total
    expect(w.text()).toContain('3') // overdue
  })

  it('baseParams 变更触发重拉', async () => {
    const w = mountPanel()
    await flushPromises()
    gwo.mockClear()
    await w.setProps({ baseParams: { date_from: '2026-02-01', date_to: '2026-02-28', asset_id: 'a1' } })
    await flushPromises()
    expect(gwo).toHaveBeenCalledWith({ date_from: '2026-02-01', date_to: '2026-02-28', asset_id: 'a1' })
  })

  it('导出按钮调 exportAnalytics(work-orders, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(exp).toHaveBeenCalled()
    expect(exp.mock.calls[0][0]).toBe('work-orders')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- WorkOrdersPanel` → FAIL。

- [ ] **Step 3: 实现 `WorkOrdersPanel.vue`**

按「面板任务通用约定」，delta：
- import：`getWorkOrderAnalytics`、`exportAnalytics`、`BaseChart`、`KpiCard`、`listAssetsMini`、`listUsers`、`ElMessage`、types。
- 常量：`WO_STATUS_LABELS: Record<string,string> = { OPEN:'待处理', IN_PROGRESS:'进行中', ON_HOLD:'挂起', COMPLETE:'已完成', CANCELED:'已取消' }`；`PRIORITY_LABELS = { NONE:'无', LOW:'低', MEDIUM:'中', HIGH:'高' }`。label 用 `LABELS[k] ?? k` 回退。
- state：`data = ref<WorkOrderAnalytics | null>(null)`、`loading`、`assetsMini`、`users`；onMounted 拉 assetsMini/users（也可在 fetch 里并行，但 mini 只需拉一次——放 onMounted）。
- `fetch`/`watch(baseParams,immediate)`/`buildParams`（剔除 undefined）。
- KPI 行（KpiCard）：总数(total)、完成率(`(completion_rate*100).toFixed(1)` unit '%')、逾期(overdue)、平均周期(`hrs(avg_cycle_time_hours)` unit 'h')、平均响应(`hrs(avg_response_time_hours)` unit 'h')。
- 图表（BaseChart）：
  - 饼图 by_status：`option` series type 'pie'，data = Object.entries(by_status).map(([k,v]) => ({ name: WO_STATUS_LABELS[k]??k, value: v }))。
  - 柱图 by_priority：x = 优先级中文，y = 计数。
  - 柱图 by_asset Top：x = `assetName(row.asset_id)`，y = count（取前 10）。
  - 柱图 by_user Top：x = `userName(row.user_id)`，y = count（前 10）。
  - 各 option 用 computed，data 为 null 返回 `{ series: [] }`。
- 顶部「导出CSV」按钮 → `exportAnalytics('work-orders', buildParams())`。
- 模板 `v-loading="loading"`。

- [ ] **Step 4: 跑绿 + 门禁** `npm run test -- WorkOrdersPanel && npm run test && npm run typecheck && npm run lint`。prettier 两文件。

- [ ] **Step 5: commit**
```bash
git add src/views/analytics/panels/WorkOrdersPanel.vue tests/unit/WorkOrdersPanel.spec.ts
git commit -m "feat(fe-analytics): work orders panel

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 成本面板 CostsPanel

**Files:** Create `src/views/analytics/panels/CostsPanel.vue`；Test `tests/unit/CostsPanel.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/CostsPanel.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: { name: 'BaseChart', props: ['option', 'height'], template: '<div class="chart-stub" />' },
}))
const { gc, exp } = vi.hoisted(() => ({ gc: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getCostAnalytics: gc, exportAnalytics: exp }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]) }))

import CostsPanel from '@/views/analytics/panels/CostsPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  parts_consumption_cost: '1200.00',
  consumption_by_part: [{ part_id: 'p1', custom_id: 'P-001', name: '轴承', qty: '10', cost: '500.00' }],
  consumption_by_asset: [{ asset_id: 'a1', cost: '500.00' }],
  po_spend_approved: '3000.00',
  po_spend_by_vendor: [{ vendor_id: 'v1', spend: '3000.00' }],
  labor_cost: '800.00',
  additional_cost: '200.00',
  total_maintenance_cost: '2200.00',
  maintenance_cost_by_asset: [
    { asset_id: 'a1', parts_cost: '500.00', labor_cost: '800.00', additional_cost: '200.00', total: '1500.00' },
  ],
}

function mountPanel() {
  return mount(CostsPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gc.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('CostsPanel', () => {
  it('加载并渲染 KPI + 备件消耗明细表', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gc).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31' })
    expect(w.text()).toContain('2200.00') // total_maintenance_cost
    expect(w.text()).toContain('轴承') // consumption_by_part name
  })

  it('导出按钮调 exportAnalytics(costs, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('costs')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- CostsPanel` → FAIL。

- [ ] **Step 3: 实现 `CostsPanel.vue`**：
- import `getCostAnalytics`/`exportAnalytics`/`BaseChart`/`KpiCard`/`listAssetsMini`/types。
- KPI：总维护成本(total_maintenance_cost)、备件消耗(parts_consumption_cost)、人工(labor_cost)、额外(additional_cost)、采购承诺(po_spend_approved)，均金额 string 直接渲染。
- 图表：堆叠柱(maintenance_cost_by_asset：x=`assetName(asset_id)`，三 series parts/labor/additional `stack:'total'`，值 `Number(row.parts_cost)` 等)；柱图(po_spend_by_vendor：x=vendor_id，y=`Number(spend)`)。
- 表(consumption_by_part)：列 编号(custom_id)/名称(name)/数量(qty)/成本(cost)。
- 导出 `exportAnalytics('costs', buildParams())`。

- [ ] **Step 4: 跑绿 + 门禁**。**Step 5: commit** `feat(fe-analytics): costs panel`（同 T2 格式 + Co-Authored-By）。

---

## Task 4: 资产可靠性面板 AssetReliabilityPanel

**Files:** Create `src/views/analytics/panels/AssetReliabilityPanel.vue`；Test `tests/unit/AssetReliabilityPanel.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/AssetReliabilityPanel.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: { name: 'BaseChart', props: ['option', 'height'], template: '<div class="chart-stub" />' },
}))
const { gar, exp } = vi.hoisted(() => ({ gar: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getAssetReliabilityAnalytics: gar, exportAnalytics: exp }))
vi.mock('@/api/assetCategories', () => ({ listAssetCategories: vi.fn().mockResolvedValue([{ id: 'ac1', name: '泵类' }]) }))

import AssetReliabilityPanel from '@/views/analytics/panels/AssetReliabilityPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  window_hours: 2160,
  assets: [
    {
      asset_id: 'a1',
      custom_id: 'AS-001',
      name: '主泵',
      availability_pct: 97.5,
      downtime_count: 2,
      total_downtime_hours: 54,
      mttr_hours: 27,
      mtbf_hours: 1053,
      total_maintenance_cost: '1500.00',
      acquisition_cost: '50000.00',
      cost_to_value_ratio: 0.03,
    },
  ],
  fleet_availability_pct: 97.5,
  fleet_total_downtime_hours: 54,
  fleet_mttr_hours: 27,
  fleet_mtbf_hours: 1053,
  fleet_total_maintenance_cost: '1500.00',
}

function mountPanel() {
  return mount(AssetReliabilityPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gar.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('AssetReliabilityPanel', () => {
  it('加载并渲染车队 KPI + 资产表（MTTR/MTBF）', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gar).toHaveBeenCalled()
    expect(w.text()).toContain('主泵') // asset row
    expect(w.text()).toContain('AS-001')
    expect(w.text()).toContain('27') // mttr
    expect(w.text()).toContain('1053') // mtbf
  })

  it('导出按钮调 exportAnalytics(asset-reliability, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('asset-reliability')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- AssetReliabilityPanel` → FAIL。

- [ ] **Step 3: 实现 `AssetReliabilityPanel.vue`**：
- import `getAssetReliabilityAnalytics`/`exportAnalytics`/`BaseChart`/`KpiCard`/`listAssetCategories`/types。
- **面板内分类过滤**：`categoryId = ref('')` + `el-select`（options=assetCategories，clearable，`@change="fetch"`）。`buildParams` 叠加 `category_id: categoryId.value || undefined`。
- KPI：车队可用率(`pct(fleet_availability_pct)` unit '%' null→'—')、车队 MTTR(`hrs(fleet_mttr_hours)` unit 'h')、车队 MTBF(`hrs(fleet_mtbf_hours)` unit 'h')、总停机(`fleet_total_downtime_hours.toFixed(1)` unit 'h')、总维护成本(fleet_total_maintenance_cost)。
- 主表(assets)：列 编号/名称/可用率(`pct(availability_pct)`%)/MTTR(`hrs`)/MTBF(`hrs`)/停机次数(downtime_count)/停机h(`total_downtime_hours.toFixed(1)`)/维护成本(total_maintenance_cost)/价值比(`cost_to_value_ratio==null?'—':cost_to_value_ratio.toFixed(3)`)。
- 柱图(各资产 availability_pct)：x=name，y=availability_pct。
- 导出 `exportAnalytics('asset-reliability', buildParams())`。

- [ ] **Step 4 跑绿+门禁。Step 5 commit** `feat(fe-analytics): asset reliability panel`。

---

## Task 5: 库存面板 InventoryPanel（ABC 帕累托）

**Files:** Create `src/views/analytics/panels/InventoryPanel.vue`；Test `tests/unit/InventoryPanel.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/InventoryPanel.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: { name: 'BaseChart', props: ['option', 'height'], template: '<div class="chart-stub" />' },
}))
const { gi, exp } = vi.hoisted(() => ({ gi: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getInventoryAnalytics: gi, exportAnalytics: exp }))
vi.mock('@/api/partCategories', () => ({ listPartCategories: vi.fn().mockResolvedValue([{ id: 'pc1', name: '轴承类' }]) }))

import InventoryPanel from '@/views/analytics/panels/InventoryPanel.vue'

const data = {
  total_inventory_value: '99999.00',
  inventory_value_by_category: [{ category_id: 'pc1', name: '轴承类', value: '60000.00' }],
  low_stock_count: 4,
  low_stock_items: [
    { part_id: 'p1', custom_id: 'P-001', name: '深沟球轴承', quantity: '3', min_quantity: '5', shortfall: '2' },
  ],
  top_consumed_parts: [{ part_id: 'p1', custom_id: 'P-001', name: '深沟球轴承', qty: '40' }],
  abc_classification: [
    { part_id: 'p1', custom_id: 'P-001', name: '深沟球轴承', consumption_value: '8000.00', cumulative_pct: 80, abc_class: 'A' },
  ],
  abc_summary: { A: 1, B: 0, C: 0 },
}

function mountPanel(
  params: Record<string, string | undefined> = { date_from: '2026-01-01', date_to: '2026-03-31' },
) {
  return mount(InventoryPanel, {
    props: { baseParams: params },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gi.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('InventoryPanel', () => {
  it('加载并渲染 KPI（库存总值/低库存数）+ 低库存表', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gi).toHaveBeenCalled()
    expect(w.text()).toContain('99999.00')
    expect(w.text()).toContain('4') // low_stock_count
    expect(w.text()).toContain('深沟球轴承')
  })

  it('库存端点只发 date 键（剔除 asset/location）', async () => {
    mountPanel({ date_from: '2026-01-01', date_to: '2026-03-31', asset_id: 'a1', location_id: 'l1' })
    await flushPromises()
    expect(gi).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31' })
  })

  it('导出按钮调 exportAnalytics(inventory, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('inventory')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- InventoryPanel` → FAIL。

- [ ] **Step 3: 实现 `InventoryPanel.vue`**：
- import `getInventoryAnalytics`/`exportAnalytics`/`BaseChart`/`KpiCard`/`listPartCategories`/types。
- **面板内备件分类过滤** `categoryId`（el-select options=partCategories，`@change="fetch"`）。
- `buildParams`：库存端点只认 `date_from`/`date_to`/`category_id` —— **只取这三键**（从 baseParams 取 date_from/date_to，叠加 category_id；忽略 asset_id/location_id）。
- KPI：库存总值(total_inventory_value)、低库存数(low_stock_count)、A类数(`abc_summary.A ?? 0`)。
- 图表：
  - **ABC 帕累托**（BaseChart 单 option，双 Y 轴）：x = abc_classification.map(name)；series1 type 'bar' yAxisIndex 0 data=consumption_value 转 Number；series2 type 'line' yAxisIndex 1 data=cumulative_pct；yAxis = [{type:'value'},{type:'value', max:100, axisLabel:{formatter:'{value}%'}}]。
  - 饼图(inventory_value_by_category)：data = map({ name: name ?? '未分类', value: Number(value) })。
  - 柱图(top_consumed_parts)：x=name，y=Number(qty)。
- 表(low_stock_items)：列 编号/名称/库存(quantity)/最低(min_quantity)/缺口(shortfall)。
- 导出 `exportAnalytics('inventory', buildParams())`。

- [ ] **Step 4 跑绿+门禁。Step 5 commit** `feat(fe-analytics): inventory panel with ABC pareto`。

---

## Task 6: 请求面板 RequestsPanel

**Files:** Create `src/views/analytics/panels/RequestsPanel.vue`；Test `tests/unit/RequestsPanel.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/RequestsPanel.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: { name: 'BaseChart', props: ['option', 'height'], template: '<div class="chart-stub" />' },
}))
const { gr, exp } = vi.hoisted(() => ({ gr: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getRequestAnalytics: gr, exportAnalytics: exp }))

import RequestsPanel from '@/views/analytics/panels/RequestsPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  total: 30,
  by_status: { PENDING: 5, APPROVED: 20, REJECTED: 3, CANCELED: 2 },
  by_priority: { HIGH: 6, MEDIUM: 15, LOW: 7, NONE: 2 },
  received: 30,
  resolved: 25,
  converted: 20,
  avg_resolution_cycle_hours: 12.3,
}

function mountPanel() {
  return mount(RequestsPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gr.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('RequestsPanel', () => {
  it('加载并渲染 KPI（总数/解决/转工单）', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gr).toHaveBeenCalled()
    expect(w.text()).toContain('30') // total
    expect(w.text()).toContain('25') // resolved
    expect(w.text()).toContain('20') // converted
  })

  it('导出按钮调 exportAnalytics(requests, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('requests')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- RequestsPanel` → FAIL。

- [ ] **Step 3: 实现 `RequestsPanel.vue`**：
- import `getRequestAnalytics`/`exportAnalytics`/`BaseChart`/`KpiCard`/types。
- 常量：`REQUEST_STATUS_LABELS = { PENDING:'待审批', APPROVED:'已批准', REJECTED:'已驳回', CANCELED:'已取消' }`；`PRIORITY_LABELS`（同前）。`LABELS[k] ?? k` 回退。
- KPI：总数(total)、解决(resolved)、转工单(converted)、平均解决周期(`hrs(avg_resolution_cycle_hours)` unit 'h')。
- 图表：饼图(by_status，中文映射)、柱图(by_priority，中文映射)、对照柱(x=['收到','解决','转化']，y=[received,resolved,converted])。
- 导出 `exportAnalytics('requests', buildParams())`。

- [ ] **Step 4 跑绿+门禁。Step 5 commit** `feat(fe-analytics): requests panel`。

---

## Task 7: 人员面板 PersonnelPanel

**Files:** Create `src/views/analytics/panels/PersonnelPanel.vue`；Test `tests/unit/PersonnelPanel.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/PersonnelPanel.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: { name: 'BaseChart', props: ['option', 'height'], template: '<div class="chart-stub" />' },
}))
const { gp, exp } = vi.hoisted(() => ({ gp: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getPersonnelAnalytics: gp, exportAnalytics: exp }))

import PersonnelPanel from '@/views/analytics/panels/PersonnelPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  users: [
    { user_id: 'u1', name: '张三', created_count: 10, completed_count: 8, assigned_count: 12, labor_hours: 40.5, labor_cost: '2025.00' },
  ],
}

function mountPanel() {
  return mount(PersonnelPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31', asset_id: 'a1' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gp.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('PersonnelPanel', () => {
  it('加载并渲染人员表（只发 date 键）', async () => {
    const w = mountPanel()
    await flushPromises()
    // personnel 端点只认 date_from/date_to，asset_id 应被剔除
    expect(gp).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31' })
    expect(w.text()).toContain('张三')
    expect(w.text()).toContain('40.5') // labor_hours
    expect(w.text()).toContain('2025.00') // labor_cost
  })

  it('导出按钮调 exportAnalytics(personnel, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('personnel')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- PersonnelPanel` → FAIL。

- [ ] **Step 3: 实现 `PersonnelPanel.vue`**：
- import `getPersonnelAnalytics`/`exportAnalytics`/`BaseChart`/`KpiCard`/types。
- `buildParams`：**只取 date_from/date_to**（personnel 端点只认日期；剔除 asset/location）。导出同样只传 date 键。
- 主表(users)：列 姓名(`row.name ?? '—'`)/创建数(created_count)/完成数(completed_count)/被指派数(assigned_count)/工时(`labor_hours.toFixed(1)`)/工时成本(labor_cost)。
- 柱图(完成数 by 姓名)：x=users.map(name)，y=completed_count。
- 导出 `exportAnalytics('personnel', buildParams())`。

- [ ] **Step 4 跑绿+门禁。Step 5 commit** `feat(fe-analytics): personnel panel`。

---

## Task 8: 趋势面板 TrendsPanel

**Files:** Create `src/views/analytics/panels/TrendsPanel.vue`；Test `tests/unit/TrendsPanel.spec.ts`

- [ ] **Step 1: 写失败测试 `tests/unit/TrendsPanel.spec.ts`**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: { name: 'BaseChart', props: ['option', 'height'], template: '<div class="chart-stub" />' },
}))
const { gt, exp } = vi.hoisted(() => ({ gt: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getTrendAnalytics: gt, exportAnalytics: exp }))

import TrendsPanel from '@/views/analytics/panels/TrendsPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  granularity: 'day',
  buckets: [
    { bucket_start: '2026-01-01', work_orders_created: 3, work_orders_completed: 2, requests_received: 5, requests_resolved: 4 },
  ],
}

function mountPanel() {
  return mount(TrendsPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gt.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('TrendsPanel', () => {
  it('加载默认 day 粒度并调端点', async () => {
    mountPanel()
    await flushPromises()
    expect(gt).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31', granularity: 'day' })
  })

  it('切换周粒度重拉 granularity=week', async () => {
    const w = mountPanel()
    await flushPromises()
    gt.mockClear()
    const vm = w.vm as any
    vm.granularity = 'week'
    await vm.fetch()
    await flushPromises()
    expect(gt).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31', granularity: 'week' })
  })

  it('导出按钮调 exportAnalytics(trends, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('trends')
  })
})
```

- [ ] **Step 2: 跑红** `npm run test -- TrendsPanel` → FAIL。

- [ ] **Step 3: 实现 `TrendsPanel.vue`**：
- import `getTrendAnalytics`/`exportAnalytics`/`BaseChart`/types。
- `granularity = ref<'day'|'week'>('day')`；`el-radio-group`（日/周，`@change="fetch"`）。
- `buildParams`：取 date_from/date_to + `granularity: granularity.value`（剔除 asset/location）。
- `fetch` 暴露：`defineExpose({ granularity, fetch })`（测试驱动切换粒度）。
- 折线图（BaseChart）：x = buckets.map(bucket_start)；四 series（工单创建/工单完成/请求收到/请求解决）type 'line'，data 对应字段。legend 中文。
- 导出 `exportAnalytics('trends', buildParams())`。

- [ ] **Step 4 跑绿+门禁。Step 5 commit** `feat(fe-analytics): trends panel`。

---

## Task 9: RBAC 门控核对 + 收尾

**Files:** 跨 views/components（核对）；Test：跑全量

- [ ] **Step 1:** 门控核对：
  - `grep -rn "hasPermission('" src/views/analytics/ src/components/AppSidebar.vue`，确认分析仪表盘门控 `analytics.view` 与后端 `backend/app/permissions.py` 的 `ANALYTICS_VIEW` 值精确一致。
  - 路由 `/analytics` 的 `meta.requiredPermission` 为 `analytics.view`。
  - 导出/各面板不单独门控（整页已门控）。
- [ ] **Step 2:** 导航/路由一致性：AppSidebar「洞察」组「分析仪表盘」path `/analytics`、无 soon、`v-if analytics.view`；「通知中心」仍 soon；`activeMenu` 对 `/analytics` 高亮；与 router path 一致。
- [ ] **Step 3:** 全量门禁：
  ```
  cd frontend && npm run test && npm run typecheck && npm run lint && npx prettier --check "src/**/*.{ts,vue}" "tests/**/*.ts"
  ```
  test 全绿、typecheck 0 错、lint 0 警告；prettier 关注本分支 `git diff main...HEAD --name-only` 的 .ts/.vue。
  > 后端无改动，不跑后端门禁。
- [ ] **Step 4: commit**（若有修正）：`chore(fe-analytics): RBAC gating audit + wrap-up`。若全部正确无改动，不造空 commit，汇报「核对通过」。

---

## 收尾

完成 T1–T9 后派发最终 code review，再用 `superpowers:finishing-a-development-branch`（合并/push 交人决定，不自动 push、不自合 main）。**本轮无 alembic 迁移**，合并 `--no-ff`。

**自查清单：**
- echarts/vue-echarts 接入，`BaseChart` 唯一渲染出口（按需注册 Bar/Line/Pie）。
- 7 面板各：KPI 卡 + 图表 + （部分）表 + 导出CSV；图表经 BaseChart；空数据安全 option。
- 全局过滤栏（日期默认 90 天 + 资产 + 位置）；库存/资产可靠性面板自带分类过滤；personnel/trends 只发 date（+granularity）键。
- CSV 导出经 axios blob（非 window.open）；文件名 `{dashboard}.csv`。
- baseParams 变更各面板重拉；惰性 tab。
- RBAC：整页门控 `analytics.view`（sidebar v-if + 路由 meta）；与后端常量一致。
- 导航洞察组分析项接入、无残留 soon（通知中心仍 soon）；路由 1 条 requiresAuth。
- 仅中文、无新增 locale。`npm run typecheck` 0 错、`npm run lint` 0 警告、vitest 全绿、prettier 干净。
- 面板测试一律 mock `BaseChart`（jsdom 无 canvas）；`exportAnalytics` 测试 stub `URL.createObjectURL`。
