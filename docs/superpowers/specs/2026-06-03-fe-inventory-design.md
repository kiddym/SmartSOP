# 设计：FE-5 库存与采购前端（备件/采购单/供应商/客户）

- 日期：2026-06-03
- 范围：前端（Vue 3 + Element Plus + Pinia + vue-router），把已就绪的库存采购后端变成可用界面。**纯前端，无后端改动、无迁移。**
- 分支：feat/fe-inventory（基于 main）
- 基线约束：仅中文、不做 i18n（沿用现有 zh-CN，不新增 locale）；UI 走 Element Plus `el-table` + `el-dialog` 表单（非独立详情页）；状态以组件内直调 api 为主、轻 Pinia（仅复用 `auth` store 做 RBAC 门控）。净室原创。

## 1. 背景与现状

前端栈：Vue 3 + Vite + TS + Pinia + Element Plus + vue-router + vitest；`vue-tsc --noEmit` typecheck + prettier。FE-0 认证、FE-1 平台管理、FE-2 主数据已完成并合入 main。

既有约定（须遵循，FE-1/FE-2 已落定）：
- `src/api/*.ts`：薄封装 `http`（axios 实例，baseURL 已含 `/api/v1`，含 401 单飞续期、token 注入），`http.get<T>(path).then(r=>r.data)`；delete 用 `http.delete(path).then(()=>undefined)`。类型在 `src/types/*`。
- `src/store/auth.ts`：暴露 `user`（含 role_code/permissions）、getter `hasPermission(code)`（super_admin 通配 + permissions 包含）。
- `src/views/*`：页面组件；`src/router/index.ts`：扁平路由 + `meta.requiresAuth` + `authGuard`；`requiredPermission` 是合法 meta key（守卫当前不强制，UI 门控为准）。
- 导航 `src/components/AppSidebar.vue`：数据驱动 `groups`，「供应」组现有 **备件库存 / 采购单 / 供应商 / 客户** 四项均为 `soon`（待接入）。
- view 模板基准：`src/views/platform/UsersView.vue`、`src/views/maindata/LocationsView.vue`（state 分区 + onMounted 并行 fetch + el-table + 单 dialog 多模式 + submitForm try/catch/finally + 本地化 `ElMessage.error('保存失败，请重试')` + `ElMessageBox.confirm` 删除 + RBAC v-if）。
- 子组件对话框基准：`src/components/maindata/AssetCategoryManageDialog.vue`（props `visible` + emit `update:visible`/`changed`，内部表格 + 增改删，`changed` 驱动父重拉）。
- 工具：`src/utils/format.ts` 的 `formatDateTime`（null→兜底）。

后端就绪端点（均 `/api/v1`，已核实，详见 §3 契约）：备件 + 备件分类 + 采购单（头/明细行/活动/状态流转）+ 采购单分类 + 供应商 + 客户，全部 models/schemas/routers/permissions 齐全，无缺口。

## 2. 关键范围决策（brainstorm 已定）

- **消耗**：后端「库存消耗」端点嵌套在工单下（`/work-orders/{id}/part-consumptions`，权限 `part.consume`），而工单/SOP 执行前端路线图定调放最后（移动端）。**本轮不做消耗 UI**；备件页通过编辑 `quantity` 字段实现入库/校正，消耗台账留到末期工单/执行阶段。
- **范围**：一轮做完「供应」组 4 项对应 view（备件库存 / 采购单 / 供应商 / 客户）；备件分类、采购单分类作页内「管理分类」对话框。
- **采购单**：完整——CRUD + 明细行可增删改（表单内嵌可编辑子表）+ 状态流转（提交/批准/驳回/取消）+ 活动时间线展示。
- **分类**：页内「管理分类」对话框（复刻 FE-2 资产分类模式）。
- **采购单详情承载**：宽 `el-dialog`（~900px）内部分区（基本信息 / 明细行 / 活动时间线），状态流转按钮在 footer。遵循「非独立详情页」基线，与其它模块一致。

## 3. 后端契约（types 以此为准）

> Decimal 字段后端序列化为字符串（如 `cost`/`quantity`/`unit_cost`/`rate`/`total_cost`/`line_total`/`min_quantity`）→ 前端 types 用 `string`，表单用文本输入；提交时空串按字段语义省略或传 "0"。日期 `expected_delivery_date` 为 `YYYY-MM-DD` 字符串或 null；时间戳 ISO 字符串。

### 3.1 备件 Part
- `PartRead`：`{id, custom_id, name, description, cost, quantity, min_quantity, unit, barcode|null, non_stock, is_low_stock, category_id|null, assignee_ids[], team_ids[], asset_ids[], location_ids[], pm_ids[]}`（数值字段字符串；`is_low_stock` 只读 computed bool）。
- `PartCreate`：`{name, description?, cost?, quantity?, min_quantity?, unit?, barcode?|null, non_stock?, category_id?|null, assignee_ids?[], team_ids?[], asset_ids?[], location_ids?[], pm_ids?[]}`。`PartUpdate`=全可选。`PartMini`=`{id, name, custom_id}`。
- 端点：`GET /parts`（查询参数 `category_id`/`asset_id`/`low_stock`，无参=全量）、`POST /parts`、`GET /parts/mini`、`GET/PATCH/DELETE /parts/{id}`。权限 `part.view/create/edit/delete`。
- 备件分类 `PartCategoryRead`=`{id, name, description}`；Create/Update `{name, description?}`。端点 `GET /part-categories`、`POST`、`GET/PATCH/DELETE /part-categories/{id}`。权限 `part_category.view`（读）/ `part_category.manage`（增改删）。
- **本轮 UI 仅用到**：part 主 CRUD + mini 关联选择 + low_stock 过滤 + part 分类对话框。关联多选数据来源：资产 `GET /assets/mini`、位置 `GET /locations/mini`、用户 `GET /users`、团队 `GET /teams`（PM 关联 `pm_ids` 本轮表单**不做**——PM 前端属 FE-4，未就绪；`pm_ids` 提交时传 `[]` 或省略）。

### 3.2 采购单 Purchase Order
- `PurchaseOrderStatus` 枚举 5 值：`DRAFT / SUBMITTED / APPROVED / REJECTED / CANCELED`。
- `POLineCreate`：`{part_id, quantity, unit_cost?}`（quantity/unit_cost 字符串）。`POLineRead`：`{id, part_id, quantity, unit_cost, line_total}`（line_total 只读 computed）。
- `PurchaseOrderCreate`：`{vendor_id, notes?, category_id?|null, shipping_address?, shipping_method?, terms_of_payment?, expected_delivery_date?|null, lines?: POLineCreate[]}`。`PurchaseOrderUpdate`=全可选（lines 全量替换）。
- `PurchaseOrderRead`：`{id, custom_id, vendor_id, status, notes, category_id|null, shipping_address, shipping_method, terms_of_payment, expected_delivery_date|null, resolution_note, resolved_by_user_id|null, resolved_at|null, lines: POLineRead[], total_cost}`。`PurchaseOrderMini`：`{id, custom_id, vendor_id, status}`。
- `POActivityRead`：`{id, activity_type, actor_user_id|null, from_status|null, to_status|null, comment, created_at}`。
- `POResolve`（批准/驳回/取消 body）：`{note?}`。
- 端点：`GET /purchase-orders`（查询 `status`/`vendor_id`）、`POST`、`GET /purchase-orders/mini`、`GET/PATCH/DELETE /purchase-orders/{id}`、`POST /purchase-orders/{id}/submit`、`POST /{id}/approve`、`POST /{id}/reject`、`POST /{id}/cancel`、`GET /{id}/activities`。
- 状态机：`DRAFT→SUBMITTED→(APPROVED|REJECTED|CANCELED)`；`DRAFT→CANCELED`；`SUBMITTED→CANCELED`。终态无出边。**PATCH 仅 DRAFT 允许**（非 DRAFT 表单字段只读）。批准时后端自动逐行回写库存。
- 权限：`purchase_order.view/create/edit/delete/approve`（submit/cancel 用 edit，approve/reject 用 approve）。
- 采购单分类 `PurchaseOrderCategoryRead`=`{id, name, description}`；Create/Update `{name, description?}`。端点 `GET /purchase-order-categories`、`POST`、`GET/PATCH/DELETE /{id}`。权限 `purchase_order_category.view`/`purchase_order_category.manage`。

### 3.3 供应商 Vendor
- `VendorRead`：`{id, name, vendor_type, description, rate, address, phone, email, website, part_ids[], asset_ids[], location_ids[]}`（rate 字符串）。`VendorCreate`：`{name, vendor_type?, description?, rate?, address?, phone?, email?, website?, part_ids?[], asset_ids?[], location_ids?[]}`。`VendorUpdate`=全可选。`VendorMini`=`{id, name}`。
- 端点：`GET /vendors`（查询 `part_id`）、`POST`、`GET /vendors/mini`、`GET/PATCH/DELETE /vendors/{id}`。权限 `vendor.view/create/edit/delete`。

### 3.4 客户 Customer
- `CustomerRead`：同 Vendor 结构 + `billing_currency`（结算货币裸码字符串）。`CustomerCreate/Update` 同 Vendor + `billing_currency?`。`CustomerMini`=`{id, name}`。
- 端点：`GET /customers`（查询 `part_id`）、`POST`、`GET /customers/mini`、`GET/PATCH/DELETE /customers/{id}`。权限 `customer.view/create/edit/delete`。

## 4. 四子模块（前端）

通用：每子模块 = `api/<x>.ts` + 类型（集中 `types/inventory.ts`）+ `views/inventory/<X>View.vue`（`el-table` 列表 + `el-dialog` 增改表单）+ 路由 + 导航接线 + RBAC 门控。列表加载/增删改后刷新；错误走 http 统一 toast，写动作 submitForm 内本地化 `ElMessage.error`。全部**扁平表格**。

### 4.1 备件库存 `/inventory/parts`
- 列：编号(custom_id)、名称、分类(category_id→PartCategory.name 映射)、库存数量(quantity)、单位(unit)、单价(cost)、低库存(`is_low_stock` → `el-tag type="danger"`「低库存」，否则空)、操作。
- 顶部：`新建备件`(part.create)、`管理分类`(打开 PartCategoryManageDialog)、低库存过滤开关(`el-switch`/checkbox → `listParts({ low_stock: true })`)。
- 表单（全字段分组）：基本(名称必填「请输入名称」、描述、分类 clearable)、库存(库存数量=入库/校正、最低库存阈值、单位、单价、非库存开关 `non_stock`)、标识(条码)、关联(资产/位置 多选来自 mini、负责人/团队 多选来自 users/teams)。保存按钮「保存」。
- 门控：part.view/create/edit/delete。

### 4.2 采购单 `/inventory/purchase-orders`
- 列：编号、供应商(vendor_id→VendorMini.name 映射)、状态(`el-tag` 5 态中文+颜色)、明细行数(lines.length)、总额(total_cost)、预计交付(expected_delivery_date)、操作。
- 顶部：`新建采购单`(purchase_order.create)、`管理分类`(PurchaseOrderCategoryManageDialog)、按状态/供应商过滤(`el-select` → 重拉)。
- 宽 `el-dialog`(~900px)分区：
  - **基本信息**：供应商(必选 `el-select` options=vendorsMini)、分类(clearable)、运输地址、运输方式、付款条款、预计交付(`el-date-picker type=date value-format=YYYY-MM-DD`)、备注。
  - **明细行**(可编辑子表 `el-table`)：每行 备件(`el-select` options=partsMini)、数量(input)、单价(input)、小计(只读 = 数量×单价前端计算展示)、删行按钮；底部「+ 添加明细行」。
  - **活动时间线**(仅编辑态)：`el-timeline` 展示 `activities`(GET /{id}/activities)，每项 from→to 状态 + 备注 + 时间。
- 状态流转(footer，按当前状态 + 权限显隐)：
  - `提交`(status=DRAFT, purchase_order.edit) → POST /submit
  - `批准`(status=SUBMITTED, purchase_order.approve) → `ElMessageBox.confirm`「批准后将自动入库」→ POST /approve
  - `驳回`(status=SUBMITTED, purchase_order.approve) → POST /reject
  - `取消`(status∈{DRAFT,SUBMITTED}, purchase_order.edit) → POST /cancel
  - `保存`(仅 status=DRAFT 或新建, create/edit) → POST /purchase-orders 或 PATCH /{id}（含 lines 全量）
- 非 DRAFT 时基本信息字段与明细行只读(后端 PATCH 拒绝非 DRAFT)；新建默认 status=DRAFT。
- 门控：purchase_order.view/create/edit/delete/approve。

### 4.3 供应商 `/inventory/vendors`
- 列：名称、类型(vendor_type)、评分(rate)、电话(phone)、邮箱(email)、操作。
- 表单：名称(必填)、类型、描述、评分、地址、电话、邮箱、网址、关联备件/资产/位置(多选来自各 mini)。保存「保存」。
- 门控：vendor.view/create/edit/delete。

### 4.4 客户 `/inventory/customers`
- 列：名称、类型、结算货币(billing_currency)、电话、邮箱、操作。
- 表单：同供应商 + 结算货币(`el-input` 裸码)。
- 门控：customer.view/create/edit/delete。

## 5. 分类对话框（2 个内嵌子组件）

`src/components/inventory/PartCategoryManageDialog.vue`、`PurchaseOrderCategoryManageDialog.vue`——复刻 `AssetCategoryManageDialog`：props `visible`，emit `update:visible`/`changed`；`watch(visible,{immediate:true})` 打开时拉取；主对话框「新增分类」按钮 + `el-table`(名称/描述列 + 操作) + 嵌套表单 dialog(名称必填+描述)；增改删后 `ElMessage.success` + 重拉 + `emit('changed')`；删除 `ElMessageBox.confirm`；提交 name `trim()`；try/catch 本地化。门控 `part_category.manage` / `purchase_order_category.manage`（读对应 `*.view`）。

## 6. 接线与横切

- **导航**(AppSidebar)：「供应」组 4 项去 `soon` 加 path：备件库存→`/inventory/parts`、采购单→`/inventory/purchase-orders`、供应商→`/inventory/vendors`、客户→`/inventory/customers`。`activeMenu` computed 加 `if (route.path.startsWith('/inventory/')) return route.path`。既有 spec 断言不破。
- **路由**(router/index.ts)：加 4 条懒加载 `views/inventory/*`，`meta: { title, requiresAuth: true, requiredPermission: <code.view> }`。
- **api/types**：新建 `api/{parts,purchaseOrders,vendors,customers,partCategories,purchaseOrderCategories}.ts`；类型集中 `types/inventory.ts`（全套 Read/Create/Update/Mini + `PurchaseOrderStatus` 联合类型 + `POLine*`/`POActivity*`）。
- **RBAC 门控**：统一 `auth.hasPermission(code)`（隐藏优先）。采购单状态按钮额外按 status 显隐。无后端守卫变更（后端 require_permission 已是真闸）。
- **状态/数值映射**：采购单 `STATUS_LABELS`（DRAFT 草稿/SUBMITTED 已提交/APPROVED 已批准/REJECTED 已驳回/CANCELED 已取消）+ tag type（DRAFT info / SUBMITTED warning / APPROVED success / REJECTED danger / CANCELED info）。金额/数量字符串原样传，空串按语义省略或 "0"。

## 7. 测试策略

vitest（项目已配）：
- api 层：各 `api/<x>.ts` 调用路径/参数正确（mock `@/api/http`，含查询参数与状态流转端点）。
- 组件：列表渲染、增改删 dialog 提交调用正确 api、RBAC 门控负向（无权限隐藏按钮）、映射列（分类名/供应商名/状态中文/低库存 tag）。
- 采购单专项：状态流转按钮按 status 显隐 + 点击调对应端点（submit/approve/reject/cancel）；明细行增删 + 小计计算；批准确认弹窗。
- 分类对话框：增改删 + `changed` 事件 + 门控负向。
- 门禁：`npm run test`（vitest）+ `npm run typecheck`（vue-tsc --noEmit）+ prettier 全绿。后端无改动，不跑后端门禁。

## 8. 任务切分（供 plan 细化，~7–8）

1. **共享骨架**：6 个 `api/*.ts` + `types/inventory.ts` + 4 条路由 + AppSidebar 供应组接线 + `views/inventory/` 占位页 + api 单测。
2. **供应商 View**（最简，作模板）+ 测试。
3. **客户 View**（仿供应商 + billing_currency）+ 测试。
4. **备件库存 View** + **PartCategoryManageDialog** + 测试（含低库存过滤、关联多选）。
5. **PurchaseOrderCategoryManageDialog** + 测试。
6. **采购单 View**（最复杂：宽对话框分区 + 明细行子表 + 活动时间线 + 状态流转）+ 测试。
7. **RBAC 门控统一核对 + 收尾**（typecheck/prettier/vitest 全绿，导航/路由联调）。

> T1 提供骨架；T2–T6 各子模块依赖 T1；T6 依赖 T1（采购单分类对话框 T5 可先于 T6）；T7 收尾。

## 9. 不在本轮

- 库存消耗台账 UI（嵌工单，留末期工单/执行阶段）。
- 套件（multi_part）、库存调整单/预留、序列号/批次追踪、多币种实体（billing_currency 仅裸码文本）。
- 采购单 PDF/导出、供应商评价历史。
- PM 关联（`part.pm_ids`）表单编辑（PM 前端属 FE-4，未就绪；提交传 `[]`/省略）。
- 路由级权限强制、响应式/移动端、其它前端模块（FE-4/FE-6 另轮）。
