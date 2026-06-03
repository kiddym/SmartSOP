# 设计：FE-2 主数据前端（位置 + 资产 + 分类 + 停机）

- 日期：2026-06-03
- 范围：前端（Vue 3 + Element Plus + Pinia + vue-router），把已就绪的主数据后端（位置/资产/资产分类/资产停机）变成可用界面。
- 分支：feat/fe-maindata（基于 main，FE-1 已合入）
- 基线约束：仅中文、不做 i18n（沿用 zh-CN，不新增 locale）；UI 走 Element Plus `el-table`（本阶段含树形）+ `el-dialog` 表单（非独立详情页）；组件内直调 api、轻 Pinia（仅复用 auth store 做 RBAC 门控）。净室原创。
- **纯前端，无后端改动**：位置/资产/分类/停机 CRUD 与停机树传播·自动停机后端均已就绪（资产停机传播由 backfill ③ 交付合入，merge a92c2b3）。

## 1. 背景与现状

前端栈与既有约定见 FE-1 设计（`2026-06-03-fe-platform-mgmt-design.md`）。本阶段严格沿用 FE-1 落定的模式：`src/api/*.ts` 薄封装 `http`、`src/types/*`、`src/views/*` 组件内直调 api + `onMounted` 拉取 + `el-dialog` 表单、`auth.hasPermission(code)` 做写动作门控（隐藏优先）、http 拦截器统一错误 toast。

导航 `src/components/AppSidebar.vue`「维护」组现有 工单/资产/位置/请求/预防性维护/计量 六项均为 `soon`。本阶段激活其中 **资产**、**位置** 两项。

### 后端就绪端点（均 `/api/v1`，已核实）

| 子模块 | 端点 | 权限 |
|---|---|---|
| 位置 | GET `/locations`（可选 `parent_id`，无参=全量扁平）、GET `/locations/mini`、POST、GET/PATCH/DELETE `/locations/{id}`、GET `/locations/{id}/children` | location.view / create / edit / delete |
| 资产 | GET `/assets`（可选 location_id/category_id/status/parent_id，无参=全量扁平）、GET `/assets/mini`、POST、GET/PATCH/DELETE `/assets/{id}`、GET `/assets/{id}/children` | asset.view / create / edit / delete |
| 资产分类 | GET/POST `/asset-categories`、PATCH/DELETE `/asset-categories/{id}` | asset_category.view / asset_category.manage |
| 资产停机 | POST `/assets/{id}/downtimes`、GET `/assets/{id}/downtimes`、PATCH `/assets/{id}/downtimes/{downtime_id}`（关闭，设 ended_at） | view=asset.view，写=asset.edit |

### 后端契约（已核实，前端 types 以此为准）

- **LocationRead**：`{id, custom_id, name, description, parent_id|null, address, longitude|null, latitude|null, assigned_user_ids[], team_ids[]}`。LocationCreate：`{name, description?, parent_id?, address?, longitude?, latitude?, assigned_user_ids?, team_ids?}`。LocationUpdate：同 Create 全可选。LocationMini：`{id, name, custom_id}`。
- **AssetStatus** 枚举（7 值）：`OPERATIONAL / STANDBY / MODERNIZATION / INSPECTION_SCHEDULED / COMMISSIONING / EMERGENCY_SHUTDOWN / DOWN`。UP 集合={OPERATIONAL, STANDBY, INSPECTION_SCHEDULED, COMMISSIONING}；DOWN 集合={MODERNIZATION, EMERGENCY_SHUTDOWN, DOWN}。
- **AssetRead**：`{id, custom_id, name, description, parent_id|null, location_id|null, category_id|null, status, serial_number, model, manufacturer, power, warranty_expiration_date|null, in_service_date|null, acquisition_cost|null, barcode|null, nfc_id|null, primary_user_id|null, assigned_user_ids[], team_ids[]}`。AssetCreate/Update 字段同（Update 全可选）。AssetMini：`{id, name, custom_id}`。
- **AssetCategoryRead**：`{id, name}`。Create：`{name}`。Update：`{name?}`。
- **DowntimeRead**：`{id, asset_id, started_at, ended_at|null, reason, downtime_type, source_asset_id|null}`。DowntimeCreate：`{started_at, ended_at?, reason?, downtime_type?='manual'}`。DowntimeClose：`{ended_at}`。

> 注：custom_id 由后端自动生成（per-company 序列）。日期字段 `warranty_expiration_date`/`in_service_date` 为 `date`（YYYY-MM-DD）；`started_at`/`ended_at` 为 `datetime`；`acquisition_cost` 为 Decimal（序列化为字符串）。

## 2. 范围与导航

- 激活侧栏「维护」组的 **资产**、**位置** 两项：去 `soon`、加 `path`（`/maindata/assets`、`/maindata/locations`）。不新增导航组。`activeMenu` computed 增加 `/maindata/*` 分支。
- 资产分类、停机为**资产页内子能力**（对话框），不占导航位。
- **不在本轮**：折旧（Depreciation）、平面图（FloorPlan）、条码/NFC 扫描（移动端期）；详情页（沿用 dialog 非独立页）；路由级权限强制（后端 require_permission 为真闸，前端门控仅 UX）。

## 3. 文件结构（新增）

- api：`src/api/locations.ts`、`src/api/assets.ts`、`src/api/assetCategories.ts`（复用 FE-1 的 `src/api/users.ts`、`src/api/teams.ts` 作下拉数据源）。
- 类型：`src/types/maindata.ts`（`AssetStatus` 联合 + Location*/Asset*/AssetCategory*/Downtime*）。
- 视图：`src/views/maindata/LocationsView.vue`、`src/views/maindata/AssetsView.vue`。
- 工具：树组装纯函数置于视图内或 `src/utils/tree.ts`（`buildTree` / `collectDescendantIds`），按实现需要决定（若两视图共用则抽 `utils/tree.ts`）。
- 路由：`src/router/index.ts` 加 2 条；导航：`src/components/AppSidebar.vue` 接线。

### api 函数清单（仿 fields.ts 薄封装）

- `locations.ts`：`listLocations()` GET `/locations`（无参取全量）、`listLocationsMini()` GET `/locations/mini`、`createLocation(p)` POST、`updateLocation(id,p)` PATCH `/locations/{id}`、`deleteLocation(id)` DELETE。
- `assets.ts`：`listAssets()` GET `/assets`、`listAssetsMini()` GET `/assets/mini`、`createAsset(p)` POST、`updateAsset(id,p)` PATCH、`deleteAsset(id)` DELETE、`listDowntimes(assetId)` GET `/assets/{id}/downtimes`、`addDowntime(assetId,p)` POST `/assets/{id}/downtimes`、`closeDowntime(assetId,downtimeId,p)` PATCH `/assets/{id}/downtimes/{downtimeId}`。
- `assetCategories.ts`：`listAssetCategories()` GET、`createAssetCategory(p)` POST、`updateAssetCategory(id,p)` PATCH、`deleteAssetCategory(id)` DELETE。

## 4. 位置 View `/maindata/locations`

- 树形 `el-table`（`row-key="id"` + 客户端组装 `children` + `:tree-props`），列：名称、编号(custom_id)、地址、操作。
- 顶部「新建位置」（`location.create`）；行内 编辑（`location.edit`）/删除（`location.delete`），无权限 `v-if` 隐藏。
- 对话框（el-form，create/edit 共用）字段：名称(必填)、描述、**父位置**（下拉/树选，options=位置列表；编辑时**排除自身及其后代**防环）、地址、经度(数字)、纬度(数字)、负责人(用户多选 `el-select multiple`，来自 listUsers)、团队(多选，来自 listTeams)。
- 提交 create→`createLocation`、edit→`updateLocation(id, {...})`；成功 `ElMessage.success` + 重拉 + 关闭；try/catch 本地化 `ElMessage.error`。
- 删除：`ElMessageBox.confirm` → `deleteLocation` → 重拉。

## 5. 资产 View `/maindata/assets`

- 树形 `el-table`，列：名称、编号、**状态**（`el-tag`，7 值中文标签 + UP/DOWN 配色：UP 绿/DOWN 红，或按既有 tag type 约定）、位置（按 location_id 映射 mini.name，`—` 兜底）、分类（按 category_id 映射 name）、操作（编辑/停机记录/删除）。
- 顶部：「新建资产」（`asset.create`）、「管理分类」（打开分类管理对话框，按 `asset_category.manage` 显隐其内写动作；列表读 `asset_category.view`）。
- **资产对话框（全字段分组，单滚动 el-form，用分隔小标题或 el-divider 分组）**：
  1. 基本信息：名称(必填)、描述、状态(下拉 7 值中文；旁注「切换 UP↔DOWN 将自动级联子资产状态」)。
  2. 层级与归属：父资产(下拉/树选，排除自身及后代)、位置(下拉 mini)、分类(下拉)。
  3. 设备信息：序列号、型号、制造商、功率。
  4. 采购与保修：购置成本(`el-input-number` 或带校验文本)、启用日期(`el-date-picker` date)、保修到期(date)。
  5. 标识：条码、NFC。
  6. 人员与团队：主负责人(单选 user)、分配用户(多选)、团队(多选)。
- 提交 create→`createAsset`、edit→`updateAsset(id, {...})`；成功提示+重拉+关闭。状态变更经 PATCH 由后端触发级联，前端无需特殊处理（重拉即反映后代状态变化）。
- **停机记录对话框**（每行「停机记录」动作）：`onOpen` 拉 `listDowntimes(assetId)`；表格列 开始时间/结束时间/原因/类型(manual→手动 / 其它→级联)/来源资产(source_asset_id 映射名，`—`)。底部「新增停机」（asset.edit）→ 填 started_at + reason → `addDowntime`；未结束行（ended_at=null）显「关闭」按钮 → 填 ended_at → `closeDowntime`。操作后刷新该资产停机列表（必要时重拉资产列表以反映状态）。
- **管理分类对话框**：`el-table`(name 列 + 操作) + 顶部「新增分类」；新增/编辑 `name`，删除确认。写动作 `asset_category.manage` 门控。分类增删改后刷新分类列表（供资产表单下拉与列表映射）。

## 6. 数据流与树组装

- 各 View `onMounted` 并行拉取：主列表（全量扁平）+ 辅助下拉（资产页另拉 位置 mini / 分类 / 用户 / 团队；位置页拉 用户 / 团队）。
- 纯函数 `buildTree(flat: T[]): T[]`：按 `parent_id` 组装，顶层=`parent_id==null`，递归挂 `children`；返回供 `el-table` 树形渲染（行对象注入 `children`，不污染原始 `parent_id` 等字段）。
- 纯函数 `collectDescendantIds(flat, id): Set<string>`：供父级选择器排除「自身 + 全部后代」，防止成环。
- 增删改/停机操作后：重拉对应扁平列表 + 重组装树。
- 映射：`location_id`/`category_id`/`primary_user_id`/`source_asset_id` → 名称用对应 mini/列表的 `find`（小规模线性查找即可，与 FE-1 一致）。

## 7. RBAC 门控（汇总）

| 动作 | 权限 code |
|---|---|
| 位置 列表 / 新建 / 编辑 / 删除 | location.view / location.create / location.edit / location.delete |
| 资产 列表 / 新建 / 编辑 / 删除 | asset.view / asset.create / asset.edit / asset.delete |
| 停机 新增·关闭 | asset.edit（查看 asset.view） |
| 分类 列表 / 增改删 | asset_category.view / asset_category.manage |
| 下拉数据源 | 用户 user.view、团队 team.view（读取，已登录即由后端兜底） |

写动作按钮一律 `v-if="auth.hasPermission('<code>')"`（super_admin 通配）。路由 `meta: { title, requiresAuth: true, requiredPermission }`（requiredPermission 预留，不强制）。

## 8. 错误处理 / 测试策略

- 错误：写动作 `try/catch { ElMessage.error('保存失败，请重试') } finally`，删除 `ElMessageBox.confirm` + 空 catch（取消/拦截器兜底），与 FE-1 五视图一致。
- 测试（vitest + @vue/test-utils，仿 FE-1 spec）：
  - api 层：各 `api/*.ts` 调用路径/方法/参数正确（`vi.hoisted` + `vi.mock('@/api/http')`）。
  - 组件层：树渲染（父子层级行）、增改删 dialog 提交调用正确 api 且 payload 正确、父级选择器排除自身/后代（防环）、停机对话框（列出+新增+关闭）、管理分类对话框、状态 tag 渲染、RBAC 门控（无权限隐藏写按钮）。
  - 断言精确（定位单元格/payload，避免脆弱全文匹配）。
- 门禁：`npm run test`（vitest 绿）+ `npm run typecheck`（vue-tsc --noEmit 0 错）+ prettier 干净。**无后端改动**，无 alembic 迁移，合并无需 down_revision 协调。

## 9. 任务切分（供 plan 细化，~6）

1. **前端骨架**：3 api 客户端 + `types/maindata.ts` + 2 路由 + AppSidebar 维护组接线（去 soon/加 path/activeMenu）+ 2 占位视图 + 树工具纯函数（buildTree/collectDescendantIds）+ api/工具单测。
2. **位置 View**：树形表格 + 增改删 dialog（父级防环）+ 用户/团队多选 + 门控 + 测试。
3. **资产分类对话框**（独立小任务或并入资产骨架）：分类 CRUD 对话框 + 门控 + 测试。
4. **资产 View（主体）**：树形表格 + 状态 tag + 位置/分类映射 + 全字段分组对话框（父级防环、各下拉）+ 门控 + 测试。
5. **资产停机对话框**：停机历史 + 新增手动 + 关闭未结束 + 类型/来源展示 + 测试。
6. **RBAC 门控统一核对 + 收尾**：逐 view 门控 code 核对、AppSidebar/activeMenu、全量门禁。

> 任务 1 提供骨架，2–5 依赖 1；3 可并入 4 的资产页（同视图内对话框），由 plan 决定粒度。6 收尾。

## 10. 不在本轮

- 折旧 / 平面图 / 条码 NFC 扫描（移动端期）。
- 资产/位置高级项（批量、导入、地图可视化经纬度打点）。
- 路由级权限强制。
- 响应式/移动端。
