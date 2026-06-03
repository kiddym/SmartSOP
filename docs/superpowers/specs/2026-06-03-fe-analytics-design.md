# FE-6 分析仪表盘 前端 设计方案（spec）

> 阶段：FE-6（执行路线图 FE-4 之后的下一条线）。依赖：各业务域已有数据 + 后端 analytics 聚合端点（已就绪）。**纯前端，后端 7 端点全就绪、无后端改动、无 alembic 迁移。** 引入图表库依赖 echarts + vue-echarts。

## 目标

把已就绪的 `/api/v1/analytics/*` 聚合端点变成单页分析仪表盘：管理者按时间窗 + 资产/位置过滤，查看工单吞吐、成本、资产可靠性（MTBF/MTTR）、库存（含 ABC）、请求漏斗、人员产能、趋势七块可视化，并可导出 CSV。

## 架构

- Vue 3 `<script setup lang="ts">` + Element Plus + **echarts + vue-echarts**（按需注册，CanvasRenderer）。
- 单路由 `/analytics` → `AnalyticsView.vue`（壳）：顶部全局过滤栏 + `el-tabs` 七分区，每分区一个独立面板子组件，**惰性加载**（`el-tab-pane lazy`，仅激活 tab 挂载并拉数据）。
- Pinia 仅复用 `auth` 做 RBAC；vue-router 扁平路由。
- api 薄封装（仿 `src/api/locations.ts`，baseURL 含 `/api/v1`）。
- **仅中文、不做 i18n、不新增 locale。净室原创，绝不出现 "Atlas" 字样或复制其代码/文案。**

### 新建文件

- `src/types/analytics.ts`（7 端点响应类型）。
- `src/api/analytics.ts`（7 GET + `exportAnalytics` blob 下载）。
- `src/components/analytics/BaseChart.vue`（vue-echarts 薄封装，唯一图表渲染出口 / 测试 mock 缝）。
- `src/components/analytics/KpiCard.vue`（el-card 指标卡）。
- `src/views/analytics/AnalyticsView.vue`（壳：过滤栏 + tabs）。
- `src/views/analytics/panels/{WorkOrders,Costs,AssetReliability,Inventory,Requests,Personnel,Trends}Panel.vue`（7 面板）。
- 对应 `tests/unit/*.spec.ts`。

### 修改文件

- `src/router/index.ts`：新增 `/analytics` 路由（`meta.requiredPermission: 'analytics.view'`）。
- `src/components/AppSidebar.vue`：「洞察」组「分析仪表盘」去 `soon`、挂 `/analytics`、`v-if` 门控 `analytics.view`；`activeMenu` 加 `/analytics` 分支。
- `frontend/package.json`：新增 `echarts`、`vue-echarts` 依赖（`npm install echarts vue-echarts`）。

### echarts 按需注册（BaseChart.vue 内）

```typescript
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
```
> 仅注册柱/折线/饼三种图（资产可用率用 KPI + 柱图，不用 gauge，保持精简）。ABC 帕累托用 BarChart + LineChart 双 Y 轴叠加。

### 复用资源

- `listAssetsMini`（`@/api/assets`）、`listLocationsMini`（`@/api/locations`）—— 全局过滤维度。
- `listPartCategories`（`@/api/partCategories`）—— 库存面板分类过滤；`listAssetCategories`（`@/api/assetCategories`，`AssetCategoryRead` 有 `name`）—— 资产可靠性面板分类过滤。
- `formatDate`/`formatDateTime`（`@/utils/format.ts`）。

## 后端契约（已核实，types 以此为准；Decimal→`string`、float→`number`、int→`number`、date→`string`）

### 端点（baseURL 含 `/api/v1`，前缀 `/analytics`，全部 GET，全部门控 `analytics.view`）

- `/analytics/work-orders`（查询 `date_from`/`date_to`/`asset_id`/`location_id`）→ `WorkOrderAnalytics`
- `/analytics/costs`（同上）→ `CostAnalytics`
- `/analytics/asset-reliability`（`date_from`/`date_to`/`asset_id`/`location_id`/`category_id`(资产分类)）→ `AssetReliabilityAnalytics`
- `/analytics/inventory`（`date_from`/`date_to`/`category_id`(备件分类)）→ `InventoryAnalytics`
- `/analytics/requests`（`date_from`/`date_to`/`asset_id`/`location_id`）→ `RequestAnalytics`
- `/analytics/personnel`（`date_from`/`date_to`）→ `PersonnelAnalytics`
- `/analytics/trends`（`date_from`/`date_to`/`granularity`('day'|'week')）→ `TrendAnalytics`
- `/analytics/{dashboard}/export`（同各面板参数 + `granularity`）→ `text/csv`（StreamingResponse）。`dashboard ∈ {work-orders,costs,asset-reliability,inventory,requests,personnel,trends}`。

### 响应 schema（字段精确）

```
CountRow { asset_id|null, user_id|null, category_id|null, count }   // by_asset/by_user/by_category 共享
WorkOrderAnalytics { date_from, date_to, total, by_status: Record<string,number>, by_priority: Record<string,number>, completed, completion_rate, overdue, avg_cycle_time_hours|null, avg_response_time_hours|null, by_asset: CountRow[], by_user: CountRow[], by_category: CountRow[] }
RequestAnalytics { date_from, date_to, total, by_status: Record<string,number>, by_priority: Record<string,number>, received, resolved, converted, avg_resolution_cycle_hours|null }
PartCostRow { part_id, custom_id, name, qty:string, cost:string }
AssetCostRow { asset_id|null, cost:string }
VendorSpendRow { vendor_id, spend:string }
MaintenanceCostByAssetRow { asset_id|null, parts_cost:string, labor_cost:string, additional_cost:string, total:string }
CostAnalytics { date_from, date_to, parts_consumption_cost:string, consumption_by_part: PartCostRow[], consumption_by_asset: AssetCostRow[], po_spend_approved:string, po_spend_by_vendor: VendorSpendRow[], labor_cost:string, additional_cost:string, total_maintenance_cost:string, maintenance_cost_by_asset: MaintenanceCostByAssetRow[] }
AssetReliabilityRow { asset_id, custom_id, name, availability_pct:number, downtime_count:number, total_downtime_hours:number, mttr_hours:number|null, mtbf_hours:number|null, total_maintenance_cost:string, acquisition_cost:string|null, cost_to_value_ratio:number|null }
AssetReliabilityAnalytics { date_from, date_to, window_hours:number, assets: AssetReliabilityRow[], fleet_availability_pct:number|null, fleet_total_downtime_hours:number, fleet_mttr_hours:number|null, fleet_mtbf_hours:number|null, fleet_total_maintenance_cost:string }
CategoryValueRow { category_id|null, name|null, value:string }
LowStockRow { part_id, custom_id, name, quantity:string, min_quantity:string, shortfall:string }
TopConsumedRow { part_id, custom_id, name, qty:string }
ABCRow { part_id, custom_id, name, consumption_value:string, cumulative_pct:number, abc_class:string }
InventoryAnalytics { total_inventory_value:string, inventory_value_by_category: CategoryValueRow[], low_stock_count:number, low_stock_items: LowStockRow[], top_consumed_parts: TopConsumedRow[], abc_classification: ABCRow[], abc_summary: Record<string,number> }
PersonnelRow { user_id, name|null, created_count, completed_count, assigned_count, labor_hours:number, labor_cost:string }
PersonnelAnalytics { date_from, date_to, users: PersonnelRow[] }
TrendBucket { bucket_start, work_orders_created, work_orders_completed, requests_received, requests_resolved }
TrendAnalytics { date_from, date_to, granularity:string, buckets: TrendBucket[] }
```

### 权限

单一权限 `analytics.view`（`backend/app/permissions.py`）守护全部端点。整页门控该 code。

## 共享组件

### `BaseChart.vue`
props `option: EChartsOption`、`height?: string`（默认 `'320px'`）。`<script setup>` 顶部 `import VChart from 'vue-echarts'` + 上述 `echarts.use([...])` 注册；模板 `<VChart class="chart" :option="option" autoresize :style="{ height }" />`。**所有面板图表经此渲染**——面板测试 mock 本组件即可绕开 jsdom 无 canvas。

### `KpiCard.vue`
props `label: string`、`value: string | number`、`unit?: string`、`hint?: string`。`el-card` 内：label（小字）+ value（大字 + unit）+ hint（次要）。面板顶部 KPI 行用 `el-row`/`el-col` 排布多张。

## 全局过滤栏 + 数据流

- `AnalyticsView` state：`dateRange = ref<[string,string]>([默认最近90天])`（`el-date-picker type="daterange" value-format="YYYY-MM-DD"`）、`assetId = ref('')`、`locationId = ref('')`、`activeTab = ref('work-orders')`。
- `assetsMini`/`locationsMini` onMounted 拉取供过滤下拉。
- `baseParams = computed(() => ({ date_from: dateRange.value?.[0], date_to: dateRange.value?.[1], asset_id: assetId.value || undefined, location_id: locationId.value || undefined }))`。
- `el-tabs v-model="activeTab"`，7 个 `el-tab-pane lazy`，各内嵌对应面板并传 `:base-params="baseParams"`（personnel/trends 只用日期，inventory 只用日期+自身分类，忽略多余键无害）。
- 每面板：props `baseParams`；`watch(() => props.baseParams, fetch, { immediate: true })` 拉自己的端点（构造时省略 undefined 键）。过滤变更 → baseParams 变 → 当前已挂载面板自动重拉。
- **错误/空数据**：各面板 fetch try/catch + loading；无数据时图表/表格显示空（KPI 显 0 或 '—'）。

## 七个分区面板

> 每面板：顶部 KPI 卡行 + 图表区 + （部分）明细表 + 右上「导出CSV」按钮（`exportAnalytics('<dashboard>', 当前 params)`）。金额字段 `string`，展示直接渲染（必要处可加千分位，本轮直接渲染原串即可）。资产/用户名映射：面板按需拉 `listAssetsMini`/`listUsers` 做 id→name（缺失→id 或 '—'）。

1. **工单 `WorkOrdersPanel`**（dashboard `work-orders`）：KPI(总数 total / 完成率 completion_rate% / 逾期 overdue / 平均周期 avg_cycle_time_hours / 平均响应 avg_response_time_hours)；饼图(by_status)、柱图(by_priority)、柱图(by_asset Top，asset 名映射)、柱图(by_user Top，user 名映射)。
2. **成本 `CostsPanel`**（`costs`）：KPI(总维护成本 total_maintenance_cost / 备件消耗 parts_consumption_cost / 人工 labor_cost / 额外 additional_cost / 采购承诺 po_spend_approved)；堆叠柱(maintenance_cost_by_asset 的 parts/labor/additional，asset 名映射)、柱图(po_spend_by_vendor)、表(consumption_by_part：编号/名称/数量/成本)。
3. **资产可靠性 `AssetReliabilityPanel`**（`asset-reliability`，含自身**资产分类**过滤 `listAssetCategories`）：KPI(车队可用率 fleet_availability_pct% / 车队 MTTR fleet_mttr_hours / 车队 MTBF fleet_mtbf_hours / 总停机 fleet_total_downtime_hours / 总维护成本 fleet_total_maintenance_cost)；主表(assets：编号/名称/可用率%/MTTR/MTBF/停机次数/停机h/维护成本/价值比)、柱图(各资产 availability_pct)。
4. **库存 `InventoryPanel`**（`inventory`，含自身**备件分类**过滤 `listPartCategories`；只用 date + category_id）：KPI(库存总值 total_inventory_value / 低库存数 low_stock_count / A类数 abc_summary.A)；**ABC 帕累托**(BarChart consumption_value + LineChart cumulative_pct 双 Y 轴，x=abc_classification 的 name)、饼图(inventory_value_by_category)、柱图(top_consumed_parts)、表(low_stock_items：编号/名称/库存/最低/缺口)。
5. **请求 `RequestsPanel`**（`requests`）：KPI(总数 total / 解决 resolved / 转工单 converted / 平均解决周期 avg_resolution_cycle_hours)；饼图(by_status)、柱图(by_priority)、对照柱(received/resolved/converted 三值)。
6. **人员 `PersonnelPanel`**（`personnel`，只用日期）：主表(users：姓名/创建数/完成数/被指派数/工时/工时成本，user 名直接用 row.name)、柱图(completed_count by 姓名)。
7. **趋势 `TrendsPanel`**（`trends`，日期 + 粒度）：粒度切换 `el-radio-group`(日/周，绑 granularity，变更重拉)；折线图(四序列 work_orders_created/completed + requests_received/resolved over buckets，x=bucket_start)。

## CSV 导出

- `exportAnalytics(dashboard: string, params)`：`http.get('/analytics/' + dashboard + '/export', { params, responseType: 'blob' })` → 取 `Blob` → 创建临时 `<a href=URL.createObjectURL(blob) download="${dashboard}.csv">` 触发点击 → `URL.revokeObjectURL`。
- **不可用 `window.open`**：认证是内存 bearer token，直链不带 Authorization 头会 401；必须经 axios（自动带 token）取 blob。
- 各面板「导出CSV」按钮调之，传当前面板的 params（含 granularity/category_id 等面板特有键）。

## 状态映射 / 工具

- 工单/请求状态、优先级的中文映射：饼图/柱图类目名用中文。后端 `by_status`/`by_priority` 的键是英文枚举名，前端用 label 映射 + **原键回退**（`LABELS[key] ?? key`），避免硬依赖某个枚举名拼写。本模块自带常量：
  - 优先级 NONE/LOW/MEDIUM/HIGH → 无/低/中/高；请求状态 PENDING/APPROVED/REJECTED/CANCELED → 待审批/已批准/已驳回/已取消。
  - 工单状态键的精确英文枚举名（如 IN_PROGRESS/COMPLETE 等）规划阶段从后端 `WorkOrderStatus` 核实后补全 label 映射；未覆盖键经回退仍正常显示原键，不影响功能。
- 数值展示：百分比保留 1 位（`x.toFixed(1)`）、小时数保留 1 位、金额直接渲染 string（null→'—'）。

## 测试与门禁

- `api/analytics.spec.ts`：7 端点 path/params 断言 + `exportAnalytics`（断言 `responseType:'blob'` + path）。
- `KpiCard.spec.ts`：渲染 label/value/unit/hint。
- `BaseChart.spec.ts`：烟雾测试——`vi.mock('vue-echarts')` 为 stub，挂载传 option 不报错（不验 canvas）。
- 各面板 spec：`vi.mock('@/api/analytics')` 返回 fixture + `vi.mock('@/components/analytics/BaseChart.vue')` 为 stub div；断言 KPI 文本、表格行、api 以正确 params 调用、`baseParams` 变更重拉、导出按钮触发 `exportAnalytics('<dashboard>', ...)`、空数据兜底。auth/mini 接口按需 mock。
- `AnalyticsView.spec.ts`：过滤栏渲染、tab 切换、默认日期窗、无权限场景（可由 sidebar/路由覆盖）。
- 门禁：`npm run test`（vitest）+ `npm run typecheck`（vue-tsc）+ `npm run lint`（eslint --max-warnings 0）+ prettier。后端无改动，不跑后端门禁。
- > echarts 在 jsdom 无 canvas：**所有图表经 `BaseChart`，面板测试一律 mock 之**；`BaseChart` 自身仅烟雾测试。

## 任务拆分（规划阶段定稿，约 9 个）

- **T1 依赖 + 骨架**：`npm install echarts vue-echarts`；`BaseChart`/`KpiCard`；`types/analytics.ts` + `api/analytics.ts`(7 + export)；路由 + 导航 + `AnalyticsView` 壳(过滤栏 + 7 lazy 空面板占位)；api 测试 + KpiCard/BaseChart 测试。
- **T2 工单面板** / **T3 成本面板** / **T4 资产可靠性面板** / **T5 库存面板(ABC 帕累托)** / **T6 请求面板** / **T7 人员面板** / **T8 趋势面板**：各面板 + 导出 + spec。
- **T9 RBAC 门控核对 + 收尾**：门控 `analytics.view` 与后端一致；sidebar/router path 一致；全量门禁；最终 code review。

## 红线约束

- 仅中文、不做 i18n、不新增 locale。
- 净室原创：复刻功能，绝不出现 "Atlas" 字样或复制其代码/文案。
- RBAC：`auth.hasPermission('analytics.view')` + `v-if`（super_admin 通配）；门控 code 与 `backend/app/permissions.py` 精确一致。
- 既有模式须遵循（api 薄封装 / view 仿既有 / 测试仿既有 spec）。
- 精确 `git add`，勿纳入仓库根未跟踪产物（`.claude/scheduled_tasks.lock`、`.verify-screenshots/*.png`）。
- 每任务 `npm run test` + `typecheck` + `lint` 全绿、prettier 干净后才 commit；commit message 结尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 范围外（本阶段不做）

- 工单详情/管理 UI、SOP 执行、移动端。
- 钻取联动（点图表跳明细列表）、自定义仪表盘布局、定时报表。
- 国际化 / 多语言。
- 后端改动、alembic 迁移。
