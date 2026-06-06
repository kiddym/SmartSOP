# SmartSOP × Atlas 原子级功能比对 — 缺失清单

> 比对日期：2026-06-06 ｜ 方法：6 个并行 agent 跨栈对照（Atlas = Java/Spring + React；SmartSOP = FastAPI + Vue），按语义而非字面匹配。仅对功能/行为对账，遵守净室红线，未碰 Atlas 源码。

## 全局复刻度概览

| 域 | 复刻度 | 主要缺口性质 |
|---|---|---|
| 平台/认证/用户/订阅 | ~80% | 后端就绪、前端未接线（认证辅助页/个人资料） |
| 工单 | ~78% | 日历视图/PDF报告/工作流/执行可写界面 |
| 资产/位置/计量 | ~78% | 详情页(Show)结构性缺失、折旧/平面图/计量分类整模块缺 |
| 库存/采购/供应商 | ~90% | 工单侧备件消耗前端整条缺失 |
| 请求/PM | ~88% | 请求表单字段配置整块缺、PM 排程边角字段 |
| 分析/文件/通知/导入导出 | ~70% | 实体级 CSV 导入导出完全缺失 |

---

## 🔴 高优先级缺失（影响核心可用性）

### 1. 工单侧备件消耗 — 前端整条缺失（后端就绪）
- **现状**：后端 `routers/part_consumptions.py`（`GET/POST /work-orders/{id}/part-consumptions`，含扣库存+单价快照）已就绪，但前端 `api/` 无客户端、`WorkOrderDetailView.vue` 无"备件/耗材"tab。用户在 UI 上**无法给工单登记备件消耗**。
- **类型**：前端页面 + 前端 API 客户端｜对应 Atlas `PartQuantityController` + 工单详情 part-quantity 组件

### 2. 认证辅助页 — 前端断链（后端就绪）
后端 `auth.py` 已有端点，前端 `api/auth.ts` 仅接 login/register/refresh/me：
- **忘记密码 / 重置密码页**：`POST /auth/forgot-password`、`/auth/reset-password` 无 UI → 用户无法自助找回密码
- **修改密码入口**：`POST /auth/change-password` 无任何调用入口
- **接受邀请落地页**：`POST /auth/accept-invite` 无 token 落地页 → 邀请闭环前端断链
- **类型**：前端页面 × 3

### 3. 请求表单字段配置（WorkOrderRequestConfiguration）— 整块缺失
- Atlas 可配置请求提交表单显示哪些字段、哪些必填（asset/location/primaryUser/dueDate/category/team 六字段）。SmartSOP 无任何实体/端点/前端页面。
- **类型**：后端实体 + 后端端点 + 前端设置页｜Atlas `Settings/Request/index.tsx`

---

## 🟡 中优先级缺失

### 平台/用户
- **个人资料页（UserProfile）整体缺失** — 无视图/路由，用户无法查看编辑自己资料/头像/最近活动
- **用户档案字段缺失**：`phone`、`jobTitle`、`rate`(工时费率，影响成本核算)、头像、姓名拆分
- **用户禁用端点缺失**：仅硬删除，无"禁用保留历史"（Atlas `PATCH /users/{id}/disable`）
- **公司档案字段缺失**：address/phone/website/employeesCount/logo 等公司画像
- **通用偏好开关缺失**（约9项）：businessType/language/PM提前提醒天数/laborCostInTotalCost/askFeedbackOnWOClosed 等
- **业务实体自定义字段（CustomField）缺失**：SmartSOP 仅 SOP 程序字段，工单/资产/请求无自定义字段能力
- **UiConfiguration 模块显隐开关缺失**：requests/locations/meters/vendorsAndCustomers 导航开关

### 工单
- **工单日历视图缺失** — `WorkOrdersView.vue` 仅表格，无日历/事件视图，无 `POST /work-orders/events` 端点
- **工单 PDF 报告缺失** — 无 `GET /work-orders/{id}/report`，详情页无"生成PDF报告"按钮
- **工作流引擎(Workflow)缺失** — 无条件触发动作能力（改派/改状态/挂清单），无 Settings/Workflows 页
- **执行态可写界面缺失** — `ExecutionTab.vue` 纯只读，后端 `PATCH /steps` 已就绪但前端无填值/标记完成/备注控件（部分归因移动端后移）
- **工单附件 tab 缺失** — 通用附件后端已就绪，但工单详情前端无附件上传 UI

### 资产/位置/计量
- **详情页(Show)模式整体缺位** — 资产/位置全退化为"列表+行内弹窗"，导致 work-orders/parts/files/meters/analytics/floorPlans 等关联 tab 无处承载（本域最大结构性缺口）
  - 资产详情缺：工单/关联备件/文件/计量/分析 5 个 tab
  - 位置详情缺：资产/工单/文件/平面图 4 个 tab
- **计量分类(MeterCategory)整模块缺失** — 无模型/路由/前端，Meter 无 category_id（注：资产分类已有）
- **资产富字段缺失**：area/additionalInfos/vendors/customers/parts(关联备件) 关联
- **资产/计量主图字段缺失**：image 主图（通用附件已注册 asset/location 但 meter 未注册，前端均无上传UI）
- **实体批量导入/导出缺失**（横切）：资产/位置/计量列表无导入导出按钮

### 库存采购
- **备件表单缺 vendor/customer 关联** — 反向关联表存在，但 PartCreate/Update schema 无 vendor_ids/customer_ids，备件侧无法维护
- **备件详情反查工单/资产页缺失** — 无独立备件详情页，无"该备件被哪些工单消耗/资产使用"反查
- **备件分析缺切面**：消耗 Pareto / 按工单分类消耗 / 按月趋势三个专门端点

### 请求/PM
- **请求附件/图片字段缺失** — 创建请求时无法带图片/附件（Atlas WorkOrderBase 含 image/files）
- **审批联动资产状态缺失** — 审批通过无法把关联资产置为"待检/维修中"（Atlas RequestApprove.assetStatus）
- **PM 排程 dueDateDelay 缺失** — 无"生成后N天到期"延迟偏移，无法表达"每月1号生成、给7天完成"
- **PM 排程 endsOn 缺失** — PM 无结束日期，启用后无限期生单

### 分析/导入导出
- **操作型实体批量导入缺失** — Atlas `POST /import/{work-orders,assets,locations,parts,meters}` + 模板下载，SmartSOP 的 batch_imports 仅解析 SOP Word 文档（语义完全不同）
- **实体整表 CSV 导出缺失** — Atlas `GET /export/{实体}`，SmartSOP 仅有分析面板/审计日志导出

---

## 🟢 低优先级缺失

### 平台/订阅
- 切换账户/超级账户体系(SwitchAccount/SuperAccountRelation)、座席级 upgrade/downgrade/request-upgrade、License validity 端点、邮箱验证页（注册即激活）、UserSettings 细分开关(PO更新/已派工单统计)、公司资料编辑页

### 工单
- 看板/列视图、mini DTO 搜索端点、紧急工单计数端点、按资产/位置/备件反查工单端点、Schedule 独立资源、工单字段配置(WorkOrderConfiguration)、完成签名采集、Labor/AdditionalCost 的 includeToTotal 开关、主计时器完成自动停表

### 资产/位置/计量
- 折旧(Deprecation)整模块、平面图(FloorPlan)整模块、位置地图组件、读数频率校验、读数 PATCH/DELETE、资产 archived 语义、资产 POST /search 分页搜索

### 库存采购
- 备件 image/files 附件、备件 area/additionalInfos、备件导入导出、MultiParts→工单应用按钮、PO 收货字段精度(收件人/城市/州/邮编/传真/申购人)、PO 打印/PDF/邮件、Customer billingName/billingAddress

### 请求/PM
- 请求语音描述(audioDescription)、pending 计数语义、请求分析按分类计数/逐日趋势序列、PM 提前N天提醒、排程失效自动停用、独立 Schedule 端点

### 分析/文件/通知
- 全局文件库页(Files 浏览/搜索/重命名)、文件 hidden/type 字段、移动端推送 token、分析细分图表(逐资产MTBF/停机时序/按周完工量/个人视角/UsefulLife)、移动端工单概览端点

---

## 设计替代（不算缺失，已确认）
- SOP 程序库(procedures) 取代 Atlas 扁平 Task/TaskBase/Checklist 模板库
- PartConsumption + PurchaseOrderLine 拆分取代 Atlas 单一 PartQuantity
- 通用 Attachment 多态基础设施取代 Atlas 实体专用 File 端点
- 通知存 type+params 结构化（前端渲染）取代 Atlas 存渲染好的 message
- Stripe 托管 Checkout 取代 Atlas 座席级 FastSpring 计费

## 已排除的伪缺口
- PO 级货币字段（Atlas PO 本就无货币字段）
- Vendor 自定义字段（Atlas Vendor 本就无动态自定义字段机制）
- customId 通用化（早已实现）
