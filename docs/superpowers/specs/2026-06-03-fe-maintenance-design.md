# FE-4 请求 / PM / 计量 前端 设计方案（spec）

> 阶段：FE-4（执行路线图并行三件套之后的下一条线）。依赖：认证（已就绪）。**纯前端，后端全就绪、无改动、无 alembic 迁移。**

## 目标

把已就绪的「请求审批 / 预防性维护排程 / 计量读数与触发器」后端变成可用前端界面：

- **请求（Requests）**：报修/请求的创建、审批（生成工单）、驳回、取消、活动时间线。
- **预防性维护（PM）**：周期排程的 CRUD、启用/停用、手动生成工单、活动时间线。
- **计量（Meters）**：仪表 CRUD + 读数追加历史与快速录入 + 触发器子 CRUD（边沿触发生成工单）。

自动生成的工单存后端，前端仅以「已生成工单」徽标/提示体现（工单详情 UI 留末期，不在本阶段做）。

## 架构

延续 FE-5 库存采购前端已验证的模式：

- Vue 3 `<script setup lang="ts">` + Element Plus（扁平 `el-table` 列表 + `el-dialog` 表单/详情）。
- Pinia 仅复用 `auth` store 做 RBAC 门控（`auth.hasPermission('<code>')` + `v-if`，super_admin 通配）。
- vue-router 扁平路由 + `meta.requiresAuth` + `meta.requiredPermission`。
- api 薄封装（仿 `src/api/locations.ts`：`http.get<T>(path).then(r=>r.data)`；delete 用 `.then(()=>undefined)`；baseURL 已含 `/api/v1`）。
- view 仿 `src/views/inventory/{Vendors,Parts,PurchaseOrders}View.vue`；嵌套对话框仿 `src/components/inventory/PartCategoryManageDialog.vue`。
- 测试仿 `tests/unit/*View.spec.ts`（可变 auth mock + `afterEach` 清 teleport DOM + 断言 api 调用/payload/状态显隐）。
- **仅中文、不做 i18n、不新增 locale。净室原创，绝不出现 "Atlas" 字样或复制其代码/文案。**

### 新建文件

- `src/types/maintenance.ts`（Request/PM/Meter 全部类型）。
- `src/api/{requests,preventiveMaintenances,meters}.ts`。
- `src/api/procedures` 既有文件追加 `listProceduresMini`（或在 maintenance 体系内提供薄封装）。
- `src/views/maintenance/{Requests,PreventiveMaintenances,Meters}View.vue`。
- `src/components/maintenance/MeterTriggerDialog.vue`（计量触发器嵌套对话框）。
- 对应 `tests/unit/*.spec.ts`。

### 修改文件

- `src/router/index.ts`：新增 3 条 `/maintenance/*` 路由。
- `src/components/AppSidebar.vue`：「维护」组 请求/预防性维护/计量 三项去 `soon`、挂 path；`activeMenu` 加 `/maintenance/` 分支。

### 复用资源

- `listAssetsMini`（`@/api/assets`）、`listLocationsMini`（`@/api/locations`）、`listUsers`（`@/api/users`，返回 `UserRead[]` 有 `name`）、`listTeams`（`@/api/teams`，`TeamRead[]` 有 `name`）。
- `formatDateTime`（`@/utils/format.ts`，null→兜底）。
- **procedure 下拉源**：现有 `GET /api/v1/procedures`（分页 `Page<ProcedureOut>`，`ProcedureOut` 含 `id` / `name` / `is_current` 等）。前端加薄 `listProceduresMini()`：拉取并映射为扁平 `{ id, name }[]`（仅取 `is_current` 行；分页用足够大的 `size` 取一页）。PM / 请求审批 / 触发器 的 procedure 选择器共用之，显示 `name`、提交 `id`。

## 后端契约（已核实）

> Decimal 字段 JSON 序列化为字符串 → 前端类型用 `string`。baseURL 含 `/api/v1`。

### 请求（Requests）

- **模型/Read**：`RequestRead { id, custom_id, title, description, priority, due_date|null, asset_id|null, location_id|null, status, work_order_id|null, resolution_note, resolved_by_user_id|null, resolved_at|null, created_at, updated_at }`。
- `priority`：`WorkOrderPriority = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'`。
- `status`：`RequestStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELED'`。
- **端点**：
  - `GET /requests`（查询 `status` / `priority` / `asset_id` / `location_id`）→ `RequestRead[]`
  - `GET /requests/pending` → `RequestRead[]`（本阶段列表用主端点带 `status=PENDING` 过滤即可，pending 端点可不用）
  - `POST /requests`（`RequestCreate { title, description?, priority?, due_date?, asset_id?, location_id? }`）→ 201
  - `GET /requests/{id}`、`PATCH /requests/{id}`（`RequestUpdate` 全可选）、`DELETE /requests/{id}`（204）
  - `POST /requests/{id}/approve`（`RequestApprove { note?, primary_user_id?, assignee_ids?, team_ids?, procedure_id? }`）→ `RequestRead`（生成工单，回填 `work_order_id`）
  - `POST /requests/{id}/reject`（`RequestReason { reason }`）、`POST /requests/{id}/cancel`（`RequestReason { reason }`）
  - `GET /requests/{id}/activities` → `ActivityRead[]`、`POST /requests/{id}/activities`（`CommentCreate { comment }`）→ 201
- **门控码**：GET/活动读=`request.view`；POST 创建 & PATCH 编辑=`request.create`；DELETE=`request.delete`；approve & reject=`request.approve`；cancel=`request.cancel`；评论=`request.view`。
- **生单**：approve 时把请求字段复制到工单 + 审批指派；`work_order_id` 体现已生成。

### 预防性维护（PM）

- **模型/Read**：`PMRead { id, custom_id, title, description, priority, asset_id|null, location_id|null, primary_user_id|null, procedure_id|null, start_date, frequency_unit, frequency_value, next_due_date, is_enabled, last_generated_at|null, last_work_order_id|null, assignee_ids[], team_ids[], created_at, updated_at }`。
- `frequency_unit`：`PMFrequencyUnit = 'DAY' | 'WEEK' | 'MONTH'`；`frequency_value`：整数 ≥1。
- **端点**：
  - `GET /preventive-maintenances`（查询 `is_enabled` / `asset_id` / `location_id`）→ `PMRead[]`
  - `POST`（`PMCreate`）→ 201、`GET /{id}`、`PATCH /{id}`（`PMUpdate` 全可选）、`DELETE /{id}`（204）
  - `POST /{id}/enable`、`POST /{id}/disable` → `PMRead`
  - `POST /{id}/generate` → `WorkOrderRead`（201，手动生成，不校验到期）
  - `GET /{id}/activities` → `PMActivityRead[]`、`POST /{id}/comments`（`CommentCreate`）→ 201
- **门控码**：GET/活动读/评论=`preventive_maintenance.view`；POST 创建=`preventive_maintenance.create`；PATCH 编辑=`preventive_maintenance.edit`；DELETE=`preventive_maintenance.delete`；enable/disable=`preventive_maintenance.edit`；**generate（手动生成）=`preventive_maintenance.create`**。
- **生单**：cron 到期（`next_due_date <= today`）自动生成 + 锥摆推进 next_due_date；或手动 `/generate`。`last_work_order_id` 体现最后生成。

### 计量（Meters）

- **Meter/Read**：`MeterRead { id, custom_id, name, unit, update_frequency_days|null, asset_id|null, location_id|null, created_at, updated_at }`。
- **MeterReading/Read**：`MeterReadingRead { id, meter_id, value, reading_at, recorded_by_user_id|null }`（`value` string；append-only）。
- **MeterTrigger/Read**：`TriggerRead { id, meter_id, name, comparator, threshold, is_armed, is_enabled, priority, title, description, primary_user_id|null, procedure_id|null, last_triggered_at|null, last_work_order_id|null, assignee_ids[], team_ids[] }`。
  - `comparator`：`MeterComparator = 'LESS_THAN' | 'MORE_THAN'`（中文「小于」「大于」）；`threshold` string。
- **ReadingResult**：`{ reading: MeterReadingRead, generated_work_order_ids: string[] }`。
- **端点**：
  - `GET /meters`（查询 `asset_id` / `location_id`）→ `MeterRead[]`；`POST`（`MeterCreate`）→ 201；`GET /{id}`、`PATCH /{id}`、`DELETE /{id}`（204）
  - `GET /meters/{id}/readings` → `MeterReadingRead[]`；`POST /meters/{id}/readings`（`MeterReadingCreate { value, reading_at? }`）→ `ReadingResult`（201）
  - `GET /meters/{id}/triggers` → `TriggerRead[]`；`POST`（`TriggerCreate`）→ 201；`GET /{tid}`、`PATCH /{tid}`、`DELETE /{tid}`（204）
  - `POST /meters/{id}/triggers/{tid}/enable`、`/disable` → `TriggerRead`
- **门控码**：meter GET=`meter.view`、POST=`meter.create`、PATCH=`meter.edit`、DELETE=`meter.delete`；读数 GET=`reading.view`、POST=`reading.create`；触发器 GET=`meter.view`、**POST create=`meter.create`**、PATCH=`meter.edit`、DELETE=`meter.delete`、enable/disable=`meter.edit`。
- **边沿触发**：提交读数时逐一评估启用触发器；条件满足且 `is_armed` 真→生单并解武装，条件反向→重新武装。`ReadingResult.generated_work_order_ids` 返回本次生成的工单。计量域**无活动时间线**，读数历史即审计。

## 板块设计

### 板块 1：请求 `/maintenance/requests`

- **列表列**：编号(custom_id)、标题、优先级(中文映射)、状态(`el-tag`：待审批/已批准/已驳回/已取消，配色 warning/success/danger/info)、资产(名称映射)、位置(名称映射)、到期日(formatDate)、已生成工单(work_order_id 存在→不可点 `el-tag`「已生成工单」)、操作。
- **顶部**：「新建请求」`request.create`；过滤 状态(`STATUS_OPTIONS` clearable) / 优先级 / 资产 / 位置（`@change` 重拉）。
- **新建/编辑对话框**（仅 `status==='PENDING'` 可编辑/出现编辑入口）：标题(必填)、描述、优先级、到期日(`el-date-picker` value-format YYYY-MM-DD)、资产(`el-select clearable` assetsMini)、位置(同 locationsMini)。门控编辑=`request.create`。
- **审批指派对话框**（approve，仅 PENDING + `request.approve`）：负责人(单选 users)、协办人(多选 users)、团队(多选 teams)、procedure(可选，proceduresMini)、备注 → `POST /approve`。成功 toast「审批通过，已生成工单」。
- **驳回/取消**：`ElMessageBox.prompt` 收原因 → reject(`request.approve`) / cancel(`request.cancel`)；空原因允许（后端 reason 必填则前端校验非空）。
- **活动时间线**：详情/编辑对话框内 `el-timeline` over `/activities`，底部评论输入 → `POST /activities`（`request.view` 即可评论）。
- **删除**：`request.delete`，`ElMessageBox.confirm`。

### 板块 2：预防性维护 `/maintenance/preventive-maintenances`

- **列表列**：编号、标题、资产、位置、频率(中文合成：`每 {frequency_value} {DAY:天/WEEK:周/MONTH:月}`)、下次到期(next_due_date)、状态(is_enabled→`el-tag`「启用/停用」)、最后生成工单(last_work_order_id→「已生成工单」徽标)、操作。
- **顶部**：「新建 PM」`preventive_maintenance.create`；过滤 启用状态 / 资产 / 位置。
- **新建/编辑对话框**：标题(必填)、描述、优先级、资产、位置、负责人(单选 users)、协办人(多选)、团队(多选)、procedure(可选)、首期日(start_date `el-date-picker`)、频率单位(DAY/WEEK/MONTH 下拉中文)、频率值(`el-input-number` ≥1)。`next_due_date` 只读展示（编辑时显示，后端推进）。门控 create/edit。
- **行操作**：启用/停用(`/enable`·`/disable`，`preventive_maintenance.edit`)、手动生成(`/generate`，`preventive_maintenance.create`，成功 toast「已生成工单」)、编辑、删除(`preventive_maintenance.delete`)。
- **活动时间线**：对话框内 `el-timeline` over `/activities` + 评论 `POST /comments`。

### 板块 3：计量 `/maintenance/meters` —— 宽对话框分区

- **列表列**：编号、名称、单位、资产、位置、推荐更新频率(update_frequency_days)、操作（详情/编辑、删除）。顶部「新建计量」`meter.create`；过滤 资产 / 位置。
- **新建对话框**（基本信息）：名称(必填)、单位、推荐更新频率天数(`el-input-number` 可空)、资产、位置。门控 create/edit。
- **宽详情对话框（900px）**三分区（`el-divider content-position="left"`）：
  1. **基本信息**：名称/单位/推荐频率/资产/位置（编辑模式可改，`meter.edit`）。
  2. **读数历史**：只读 `el-table`（值 / 时间(formatDateTime) / 记录人(名称映射)，倒序）。顶部**快速录入**（`reading.create`）：值(`el-input`) + 可选时间(`el-date-picker` 默认现在) + 「提交读数」→ `POST /readings`。提交后：若 `generated_work_order_ids.length > 0` → toast「本次读数触发 {N} 张工单」；刷新读数列表与触发器（`is_armed` 可能变化）。
  3. **触发器**：子表 `el-table`（名称 / 比较(中文) / 阈值 / 优先级 / 启用(is_enabled) / 武装(is_armed→「武装/已触发」只读 tag) / 操作）。「新增触发器」`meter.create` → 嵌套 `MeterTriggerDialog`；行内 编辑(`meter.edit`)、启用/停用(`meter.edit`)、删除(`meter.delete`)。
- **`MeterTriggerDialog`（嵌套对话框）**：props `visible` + `meterId` + `editing?`；字段 名称(必填)、比较符(LESS_THAN/MORE_THAN 中文下拉)、阈值(`el-input`)、优先级、生单标题、描述、负责人(单选)、协办人(多选)、团队(多选)、procedure(可选)、启用(`el-switch`)。提交 create/edit → emit `saved` 让父刷新触发器列表。
- **注**：触发器字段多，采用「子表列表 + 嵌套对话框」而非行内编辑（比 PO 明细行更重，合理取舍）。`is_armed` 只读（体现边沿去抖语义）。

## 状态/枚举映射常量

- `PRIORITY_LABELS: Record<WorkOrderPriority,string> = { NONE:'无', LOW:'低', MEDIUM:'中', HIGH:'高' }`。
- `REQUEST_STATUS_LABELS = { PENDING:'待审批', APPROVED:'已批准', REJECTED:'已驳回', CANCELED:'已取消' }`，tag 配色 `{ PENDING:'warning', APPROVED:'success', REJECTED:'danger', CANCELED:'info' }`。
- `PM_FREQUENCY_LABELS = { DAY:'天', WEEK:'周', MONTH:'月' }`。
- `COMPARATOR_LABELS = { LESS_THAN:'小于', MORE_THAN:'大于' }`。

## 测试与门禁

- 每板块 view + `MeterTriggerDialog` 各配 vitest spec：加载渲染、新建携带关键字段、状态流转/动作调用正确 api（approve/reject/cancel/enable/disable/generate/submit reading）、无权限隐藏写按钮、映射正确（状态/优先级/比较符中文、资产/用户名映射）。
- 计量读数：断言提交 `POST /readings` 后对 `ReadingResult.generated_work_order_ids` 的提示与刷新。
- 门禁：`npm run test`（vitest 全绿）+ `npm run typecheck`（vue-tsc 0 错）+ `npm run lint`（eslint --max-warnings 0）+ prettier 干净。后端无改动，不跑后端门禁。

## 任务拆分（规划阶段定稿）

- **T1 共享骨架**：`types/maintenance.ts` + 3 个 api 文件 + `listProceduresMini` + 路由 3 条 + 导航接线 + 4 个占位 view + api 单元测试。
- **T2 请求 View**：列表/过滤 + 创建编辑对话框 + 审批指派对话框 + 驳回/取消 prompt + 活动时间线/评论 + 已生成工单徽标。
- **T3 预防性维护 View**：列表/过滤 + 创建编辑（排程字段）+ 启用/停用/手动生成 + 活动时间线/评论 + 频率中文合成。
- **T4 计量 View**：列表 + 宽详情对话框（基本信息 + 读数历史/快速录入 + 触发器子表）+ `MeterTriggerDialog` 嵌套对话框 + 读数触发提示。
- **T5 RBAC 门控统一核对 + 收尾**：逐文件核对门控码与 `backend/app/permissions.py` 精确一致；sidebar/router path 一致；全量门禁；最终 code review。

## 红线约束

- 仅中文、不做 i18n、不新增 locale。
- 净室原创：复刻功能，绝不出现 "Atlas" 字样或复制其代码/文案。
- RBAC：`auth.hasPermission('<code>')` + `v-if` 隐藏（super_admin 通配）；门控 code 必须与 `backend/app/permissions.py` 精确一致（本 spec 已逐端点核实）。
- 既有模式须遵循（api 薄封装 / view 仿 inventory / 嵌套对话框仿 PartCategoryManageDialog / 测试仿既有 spec）。
- 精确 `git add`，勿纳入仓库根未跟踪产物（`.claude/scheduled_tasks.lock`、`.verify-screenshots/*.png`）。
- 每任务 `npm run test` + `typecheck` + `lint` 全绿、prettier 干净后才 commit；commit message 结尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 范围外（本阶段不做）

- 工单详情/管理 UI（留末期；本阶段仅「已生成工单」徽标/提示）。
- SOP 逐步执行、移动端。
- 国际化 / 多语言。
- 后端改动、alembic 迁移。
