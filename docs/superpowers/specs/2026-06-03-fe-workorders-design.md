# 末期① 工单管理 PC 前端 设计方案（spec）

> 阶段：末期第一子项（执行路线图「工单管理 + SOP 逐步执行 + 移动端」三子系统的第一个）。依赖：工单后端（已完整就绪）。**纯前端，后端全就绪、无后端改动、无 alembic 迁移。** SOP 逐步执行填写留移动端，PC 端执行进度**只读展示**。

## 目标

把已就绪的工单后端变成 PC 端工单管理界面：列表 + 多维过滤、工单 CRUD、状态流转、指派（用户/团队）、工时与额外成本、成本汇总、活动时间线、SOP 挂接/解绑、执行进度只读展示、工单分类管理。

## 架构

- Vue 3 `<script setup lang="ts">` + Element Plus + Pinia（auth RBAC）+ vue-router。api 薄封装（仿 `src/api/requests.ts`，baseURL 含 `/api/v1`）。
- 复用 FE-6 的 `src/components/analytics/KpiCard.vue`（成本汇总卡）。
- **两路由**：`/maintenance/work-orders`（列表 `WorkOrdersView`）+ `/maintenance/work-orders/:id`（详情 `WorkOrderDetailView`，el-tabs）。
- sidebar「维护」组「工单」去 `soon`、挂 `/maintenance/work-orders`；`activeMenu` 对 `/maintenance/work-orders` 高亮（详情页 `/maintenance/work-orders/:id` 也高亮该项，用 `startsWith('/maintenance/work-orders')`）。
- **仅中文、不做 i18n。净室原创，绝不出现 "Atlas" 字样或复制其代码/文案。**

### 新建文件

- `src/types/workOrder.ts`（工单相关全部类型；与既有 `src/types/maintenance.ts` 区分，避免后者过大）。
- `src/api/workOrders.ts`（主端点 + labor + additional-cost + cost-summary + execution + activities）、`src/api/workOrderCategories.ts`、`src/api/timeCategories.ts`（`listTimeCategories`）、`src/api/costCategories.ts`（`listCostCategories`）。
- `src/views/maintenance/WorkOrdersView.vue`（列表）、`src/views/maintenance/WorkOrderDetailView.vue`（详情壳 + tabs）。
- 详情 tab 子组件：`src/components/workorder/{OverviewTab,LaborCostTab,ActivityTab,ExecutionTab}.vue`。
- `src/components/workorder/WorkOrderFormDialog.vue`（新建/编辑工单对话框）、`src/components/workorder/LaborDialog.vue`（工时新建/编辑）、`src/components/workorder/AdditionalCostDialog.vue`（额外成本新建/编辑）、`src/components/maintenance/WorkOrderCategoryManageDialog.vue`（分类管理，仿 PartCategory）。
- 对应 `tests/unit/*.spec.ts`。

### 修改文件

- `src/router/index.ts`：新增 2 条 `/maintenance/work-orders` 路由。
- `src/components/AppSidebar.vue`：「维护」组「工单」去 soon、挂 path。

### 复用资源

- `listAssetsMini`/`listLocationsMini`/`listUsers`/`listTeams`/`listProceduresMini`、`formatDate`/`formatDateTime`、`KpiCard`。
- 状态/优先级中文映射本模块自带常量（见下）；FE-6 `WorkOrdersPanel` 有同名映射但属另一文件，本模块独立定义。

## 后端契约（已核实，types 以此为准；Decimal→`string`、int→`number`、date/datetime→`string`；baseURL 含 `/api/v1`）

### 工单状态/优先级

- `WorkOrderStatus = 'OPEN' | 'IN_PROGRESS' | 'ON_HOLD' | 'COMPLETE' | 'CANCELED'`。
- `WorkOrderPriority = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'`。
- **ALLOWED_TRANSITIONS**：`OPEN→[IN_PROGRESS, CANCELED]`；`IN_PROGRESS→[ON_HOLD, COMPLETE, CANCELED]`；`ON_HOLD→[IN_PROGRESS, CANCELED]`；`COMPLETE→[IN_PROGRESS]`（重开）；`CANCELED→[]`（终态）。

### 主端点（`/work-orders`，权限见各行）

- `GET /work-orders`（查询 `status`/`priority`/`asset_id`/`location_id`/`assignee_id`/`procedure_attached`）→ `WorkOrderRead[]`，`work_order.view`
- `POST /work-orders`（`WorkOrderCreate`）→ `WorkOrderRead`，`work_order.create`
- `GET /work-orders/{id}` → `WorkOrderRead`，`work_order.view`
- `PATCH /work-orders/{id}`（`WorkOrderUpdate`）→ `WorkOrderRead`，`work_order.edit`
- `DELETE /work-orders/{id}` → 204，`work_order.delete`
- `PUT /work-orders/{id}/assignees`（`{ user_ids: string[] }`）→ `WorkOrderRead`，`work_order.edit`（替换语义）
- `PUT /work-orders/{id}/teams`（`{ team_ids: string[] }`）→ `WorkOrderRead`，`work_order.edit`（替换语义）
- `POST /work-orders/{id}/transition`（`{ to_status, note }`）→ `WorkOrderRead`，`work_order.edit`
- `POST /work-orders/{id}/attach-procedure`（`{ procedure_id }`）→ `WorkOrderRead`，`work_order.edit`
- `DELETE /work-orders/{id}/procedure` → `WorkOrderRead`，`work_order.edit`（清执行步骤）
- `GET /work-orders/{id}/execution` → `ExecutionView`，`work_order.view`
- `GET /work-orders/{id}/activities` → `ActivityRead[]`，`work_order.view`
- `POST /work-orders/{id}/activities`（`{ comment }`）→ `ActivityRead`，`work_order.view`

### 工时/成本子端点（`/work-orders/{id}/...`）

- `GET /labor` → `LaborRead[]`，`work_order.view`
- `POST /labor`（`LaborCreate`：`duration_seconds` 必填）→ `LaborRead`，`work_order.edit`
- `POST /labor/start`（`LaborTimerStart`）→ `LaborRead`，`work_order.edit`
- `POST /labor/{laborId}/stop` → `LaborRead`，`work_order.edit`
- `PATCH /labor/{laborId}`（`LaborUpdate`）→ `LaborRead`，`work_order.edit`
- `DELETE /labor/{laborId}` → 204，`work_order.edit`
- `GET /additional-costs` → `AdditionalCostRead[]`，`work_order.view`
- `POST /additional-costs`（`AdditionalCostCreate`）→ `AdditionalCostRead`，`work_order.edit`
- `PATCH /additional-costs/{costId}`（`AdditionalCostUpdate`）→ `AdditionalCostRead`，`work_order.edit`
- `DELETE /additional-costs/{costId}` → 204，`work_order.edit`
- `GET /cost-summary` → `CostSummaryRead`，`work_order.view`

### 分类与下拉源

- `GET /work-order-categories` → `WorkOrderCategoryRead[]`，`work_order_category.view`；POST/PATCH/DELETE `work_order_category.manage`。
- `GET /time-categories` → `TimeCategoryRead[]`，`time_category.view`（labor 工时类别下拉，含 hourly_rate）。
- `GET /cost-categories` → `CostCategoryRead[]`，`cost_category.view`（额外成本类别下拉，可选）。

### 类型（字段精确）

```
WorkOrderRead { id, custom_id, title, description, status, priority, due_date|null, asset_id|null, location_id|null, primary_user_id|null, procedure_id|null, procedure_group_id|null, completed_at|null, category_id|null, created_by_user_id|null, assignee_ids[], team_ids[] }
WorkOrderCreate { title, description?, priority?, due_date?|null, asset_id?|null, location_id?|null, primary_user_id?|null, assignee_ids?, team_ids?, category_id?|null, procedure_id?|null }
WorkOrderUpdate { title?, description?, priority?, due_date?|null, asset_id?|null, location_id?|null, primary_user_id?|null, category_id?|null }   // 不含 assignee/team/procedure（走专用端点）
WorkOrderTransition { to_status: WorkOrderStatus, note? }
ActivityRead { id, activity_type, actor_user_id|null, from_status|null, to_status|null, comment, created_at }
CommentCreate { comment }
TimeCategoryRead { id, name, hourly_rate:string, description }
LaborRead { id, work_order_id, user_id|null, time_category_id|null, started_at|null, stopped_at|null, duration_seconds:number, hourly_rate:string, notes, running:boolean, cost:string, running_elapsed_seconds:number|null }   // running/cost/running_elapsed_seconds 为后端 computed
LaborCreate { duration_seconds:number, time_category_id?|null, hourly_rate?:string|null, user_id?|null, started_at?|null, stopped_at?|null, notes? }
LaborTimerStart { time_category_id?|null, hourly_rate?:string|null, user_id?|null, notes? }
LaborUpdate { duration_seconds?:number, time_category_id?|null, hourly_rate?:string|null, user_id?|null, notes? }
CostCategoryRead { id, name, description }
AdditionalCostRead { id, work_order_id, cost_category_id|null, title, amount:string, description, created_by_user_id|null }
AdditionalCostCreate { title, amount:string, cost_category_id?|null, description? }
AdditionalCostUpdate { title?, amount?:string, cost_category_id?|null, description? }
CostSummaryRead { labor_total:string, additional_total:string, parts_total:string, total:string }
OutlineNode { node_id, heading_level:number|null, kind, body, code, sort_order:number }
StepResultRead { id, node_id, node_code, node_sort_order:number, input_schema:Record<string,unknown>, response:Record<string,unknown>, is_done:boolean, done_by_user_id|null, done_at|null, notes }
ProcedureRef { id, group_id|null, code, name, version:number }
ExecutionView { procedure: ProcedureRef|null, outline: OutlineNode[], steps: StepResultRead[] }
WorkOrderCategoryRead { id, name, description }
```

> `LaborCreate.duration_seconds` 必填且后端禁止「仅 started_at（运行中）+ duration_seconds>0」矛盾组合；手填工时走 `POST /labor`（给 duration_seconds），计时器走 `POST /labor/start` → `POST /labor/{id}/stop`。`hourly_rate` 省略时后端从 `time_category` 快照。

## 状态/优先级映射常量（本模块）

```
WO_STATUS_LABELS = { OPEN:'待处理', IN_PROGRESS:'进行中', ON_HOLD:'挂起', COMPLETE:'已完成', CANCELED:'已取消' }
WO_STATUS_TAG = { OPEN:'info', IN_PROGRESS:'warning', ON_HOLD:'info', COMPLETE:'success', CANCELED:'danger' }
PRIORITY_LABELS = { NONE:'无', LOW:'低', MEDIUM:'中', HIGH:'高' }
// 流转按钮文案：to_status + from-context
TRANSITION_LABELS：OPEN→IN_PROGRESS='开始'；ON_HOLD→IN_PROGRESS='恢复'；COMPLETE→IN_PROGRESS='重开'；*→ON_HOLD='挂起'；*→COMPLETE='完成'；*→CANCELED='取消'
```

## 板块设计

### 板块 1：列表 `/maintenance/work-orders`（`WorkOrdersView`）

- **列表列**：编号(custom_id)、标题、状态(`el-tag` 配 WO_STATUS_TAG/LABELS)、优先级(中文)、资产(名称映射)、位置(名称映射)、负责人(userName)、到期(`due_date ? formatDate : '—'`)、操作（详情、删除）。
- **过滤**：状态/优先级/资产/位置/指派人(`assignee_id`，users)/是否挂 SOP(`procedure_attached` 布尔，select 全部/已挂/未挂 → `true`/`false`/省略)。`@change` 重拉。
- **顶部**：「新建工单」`work_order.create`、「管理分类」`work_order_category.view`。
- **新建工单**：`WorkOrderFormDialog`（create 模式）字段：标题(必填)、描述、优先级、到期日、资产、位置、分类、负责人、指派用户(多选)、指派团队(多选)、关联 SOP(可选 proceduresMini)。提交 `createWorkOrder`。
- 「详情」/行点击 → `router.push('/maintenance/work-orders/' + id)`。「删除」`work_order.delete` 确认 → `deleteWorkOrder`。

### 板块 2：详情页 `/maintenance/work-orders/:id`（`WorkOrderDetailView`）

- **加载**：onMounted `getWorkOrder(id)`（失败 → 提示 + 返回列表）。提供 `reload()` 供子 tab 改动后刷新工单头。
- **页头**：返回按钮、`custom_id` + 标题、状态 `el-tag`、**状态流转按钮组**（按 `ALLOWED_TRANSITIONS[current]` 动态渲染，每按钮 `work_order.edit`）、「编辑」按钮（`work_order.edit` → `WorkOrderFormDialog` edit 模式，仅基本信息字段）。
  - 流转：点击 → 可选 `ElMessageBox.prompt` 收 note（取消/完成等可加备注，简化：直接 `transition({to_status, note:''})`，但「取消」「完成」用 confirm）→ `transitionWorkOrder(id, {to_status, note})` → reload。完成失败（步骤未完成，后端报错）→ `ElMessage.error` 透出后端信息或本地化「存在未完成步骤」。
- **el-tabs**：
  - **概览 `OverviewTab`**：基本信息只读展示（编号/标题/描述/优先级/状态/资产/位置/分类/负责人/到期/创建人）；**指派**区（用户多选 + 团队多选，「保存指派」→ `setAssignees`/`setTeams` 替换，`work_order.edit`）；**SOP** 区（已挂：显示 procedure 信息 + 「解绑」`work_order.edit` confirm→`detachProcedure`；未挂：proceduresMini 选择 + 「挂接」→`attachProcedure`）。
  - **工时成本 `LaborCostTab`**：**成本汇总卡**（`KpiCard` × 4：工时合计 labor_total / 额外合计 additional_total / 备件合计 parts_total / 总计 total，`getCostSummary`）；**工时子表**（用户名/工时类别名/时长(`duration_seconds` 转「Xh Ym」或秒)/费率(hourly_rate)/成本(cost)/状态(running→「计时中」tag，否则空)/备注；操作 编辑·停止(running 时)·删除，`work_order.edit`）+ 顶部「新增工时」(`LaborDialog`)、「开始计时」(`startTimer` 快捷，可弹 LaborDialog 的计时模式)；**额外成本子表**（标题/金额/类别名/备注；操作 编辑·删除）+ 「新增成本」(`AdditionalCostDialog`)。任何增删改后 reload 子表 + 重取 cost-summary。
    - 运行中行显「计时中」tag，**不实时跳秒**（不渲染 running_elapsed_seconds 的秒级计时；移动端做实时）。
  - **活动 `ActivityTab`**：`el-timeline` over `listWorkOrderActivities`（每项 timestamp=formatDateTime；内容按 activity_type 通用渲染：STATUS_CHANGE 显示 `from→to` 中文、COMMENT 显示 comment、其余显示 activity_type + comment）+ 评论输入（`addWorkOrderComment`，`work_order.view`）。
  - **执行 `ExecutionTab`**（仅 `work_order.procedure_id` 非空时显示，**只读**）：`getExecution(id)`；展示 procedure 信息 + outline（按 sort_order，heading_level 缩进）+ steps（node_code/标题、`is_done` tag「已完成/未完成」、done_by/done_at、notes）。**PC 不提供填写**（逐步执行留移动端）。

### 板块 3：工时/成本/工单 对话框

- `WorkOrderFormDialog`：create 含全字段（含指派/SOP）；edit 仅 `WorkOrderUpdate` 字段（标题/描述/优先级/到期/资产/位置/分类/负责人）。
- `LaborDialog`：用户(users 单选)、工时类别(`listTimeCategories`，可空，选后可带出 rate 提示)、时长(手填，输入小时或秒——本轮用「分钟」`el-input-number` → 提交 `duration_seconds = minutes*60`)、费率(可空 hourly_rate，省略则后端按类别快照)、备注。create→`createLabor({duration_seconds,...})`；edit→`updateLabor`。
- `AdditionalCostDialog`：标题(必填)、金额(必填 string)、成本类别(`listCostCategories`，可空)、描述。create→`createAdditionalCost`、edit→`updateAdditionalCost`。
- `WorkOrderCategoryManageDialog`：名称+描述 CRUD（仿 `PartCategoryManageDialog`），门控 `work_order_category.manage`。

## RBAC 门控码（与后端 permissions.py 一致）

- 工单：`work_order.view/create/edit/delete`；状态流转·指派·SOP挂接解绑·labor CRUD·cost CRUD = `work_order.edit`。
- 分类：`work_order_category.view`（入口）/`work_order_category.manage`（增改删）。
- 执行 tab 只读，不涉 `work_order.execute`（该权限属移动端填写）。
- 下拉源读权限（time_category.view / cost_category.view / asset.view 等）门控从宽，本轮下拉不单独门控。

## 测试与门禁

- api 单测：主端点 + labor + additional-cost + cost-summary + execution + activities + category + timeCategories/costCategories（path/method/params/body 断言）。
- 视图/对话框 vitest：列表（过滤/新建/删除/跳详情，路由用 mock router 或 `vi.mock('vue-router')`）；详情页（状态流转按钮按 status 动态显隐、tab 渲染，复杂交互 `defineExpose` 驱动）；各 tab（概览指派/SOP、工时成本 CRUD + 汇总、活动时间线、执行只读）；分类对话框。可变 auth mock + teleport 清理。
- 门禁：`npm run test` + `typecheck` + `lint(--max-warnings 0)` + prettier。后端无改动，不跑后端门禁。

## 任务拆分（规划阶段定稿，约 8–9）

- **T1 骨架**：`types/workOrder.ts` + `api/{workOrders,workOrderCategories,timeCategories,costCategories}.ts` + 2 路由 + 导航 + 列表/详情占位 + api 测试。
- **T2 列表 View**：过滤 + `WorkOrderFormDialog`(create) + 删除 + 跳详情。
- **T3 详情壳 + 状态流转 + 概览 tab**：页头流转按钮（ALLOWED_TRANSITIONS 动态）+ 编辑（FormDialog edit）+ 概览（基本信息/指派/SOP挂接解绑）。
- **T4 工时成本 tab**：成本汇总卡 + 工时子表（CRUD + 计时器起停，不实时跳秒）+ `LaborDialog` + 额外成本子表 + `AdditionalCostDialog`。
- **T5 活动 tab**：时间线 + 评论。
- **T6 执行 tab（只读）**：outline + steps 展示。
- **T7 工单分类对话框**。
- **T8 RBAC 核对 + 收尾**：门控码与 `permissions.py` 精确一致；sidebar/router 一致；全量门禁；最终 code review。

## 红线约束

- 仅中文、不做 i18n、不新增 locale。
- 净室原创：复刻功能，绝不出现 "Atlas" 字样或复制其代码/文案。
- RBAC：`auth.hasPermission('<code>')` + `v-if`（super_admin 通配）；门控 code 与 `backend/app/permissions.py` 精确一致（本 spec 已逐端点核实）。
- 既有模式须遵循（api 薄封装 / view 仿 maintenance·inventory / 嵌套对话框仿 PartCategory / 测试仿既有 spec）。
- 精确 `git add`，勿纳入仓库根未跟踪产物（`.claude/scheduled_tasks.lock`、`.verify-screenshots/*.png`）。
- 每任务 `npm run test` + `typecheck` + `lint` 全绿、prettier 干净后才 commit；commit message 结尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 范围外（本阶段不做）

- **SOP 逐步执行填写**（移动端：扫码/拍照/签名/离线；PC 执行 tab 只读）——末期第二子项。
- **移动端**——末期第三子项。
- 工时类别/成本类别/时间类别的管理 CRUD 界面（本轮仅消费其列表作下拉；管理界面属平台配置，留后续）。
- 备件消耗（PartConsumption）子表编辑（cost-summary 的 parts_total 只读展示，编辑留库存/工单集成后续）。
- 国际化 / 多语言、后端改动、alembic 迁移。
