# Smart CMMS 总体设计与路线图（Master Roadmap Design）

- **日期**: 2026-05-30
- **状态**: 已批准（总体设计）
- **作者**: brainstorming 协作产出

---

## 1. 背景与目标

将自有的 **SmartSOP**（结构化 SOP 管理系统）与开源的 **Atlas CMMS** 的功能融合，
产出一个**可商业化、完全自有、零开源协议风险**的 **Smart CMMS** 系统。

### 核心需求

1. **SOP 作为工单执行依据**：用 SmartSOP 的结构化 SOP 替代 Atlas CMMS 工单中已有的扁平
   清单（`Task/TaskBase`），作为工单的执行依据。
2. **复刻 Atlas CMMS 全部功能**：工单、资产、位置、库存、采购、预防性维护、仪表读数、
   分析报表、多租户、订阅计费、移动端等。
3. **零协议风险**：Atlas CMMS 为 **GPL v3**（双授权：GPL v3 或付费商业授权）。本项目采用
   **净室重写（clean-room reimplementation）**，仅以 Atlas 作为功能/行为规格参考，
   不复制其任何源码/资源/品牌。
4. **商业化产物**：完全自有的专有产品，多租户 SaaS 形态。

### 已确认的关键决策

| 决策项 | 选择 |
|--------|------|
| 授权策略 | **净室重写**（以 SmartSOP 为底座，全新原创代码实现 Atlas 功能） |
| 范围 | **完整复刻 Atlas 全部模块**（拆分为多个分期子项目） |
| 部署形态 | **多租户 SaaS**（Company 为租户根，行级隔离，含订阅计费） |
| 移动端 | 需要，但**后期分期**实现 |
| 目标市场/语言 | **中文为主**，架构预留 i18n（多语言） |
| 构建架构 | **方案 A**：在 SmartSOP 仓库内扩展（SOP 引擎进程内一等公民） |

---

## 2. 两个代码库现状（事实基线）

### SmartSOP（构建底座，自有代码，无 GPL）

- **后端**: Python ≥3.11, FastAPI 0.111, SQLAlchemy 2.0（同步）, Pydantic v2, Alembic, PyMySQL；
  python-docx（Word 导入）, ReportLab（PDF）。JWT/passlib 脚手架存在但**未接线**。
- **前端**: Vue 3 `<script setup>` + TypeScript, Element Plus, Pinia, Vue Router, Vite, Tailwind, Axios。
- **SOP 领域模型（核心资产）**:
  ```
  Folder（树, ≤5 层）
    └── Procedure（SOP；code, version, status: draft/published/archived/void）
          ├── ProcedureVersion[]（不可变 JSON 快照 + 变更日志）
          └── Section（树, parent_id 自引用）
                └── Step（有序；富文本内容, 媒体, step_type）
          └── custom_field_values（JSON, 由 CustomFieldDef 驱动）
  ```
  - 生命周期：draft → published → archived，含 void/restore
  - 版本控制：整数版本 + 每版本完整 JSON 快照 + 变更日志
  - 导入：`.docx`（标准 + 智能两种模式）→ Section/Step 树
  - 导出：ReportLab PDF（封面/目录/修订页）
- **已有可复用基础设施**: AuditLog（全量审计）、Attachment（附件）、CustomFieldDef（自定义字段）。
- **缺失**: 工单/任务/执行/指派、资产/设备/位置/库存、用户/角色（未接线）、多租户。

### Atlas CMMS（行为规格参考，GPL v3，禁止复制代码）

- **后端**: Spring Boot (Java)；**前端**: React + MUI + Redux；**移动端**: React Native。
- **领域模型概念**（仅作参考）:
  - 工单管理: `WorkOrder`, `WorkOrderHistory`, `Task`, `TaskBase`（扁平清单）, `Request`,
    `PreventiveMaintenance`, `Schedule`
  - 资产与位置: `Asset`（树/状态/停机/保修）, `Location`（树/地理坐标）, `AssetDowntime`,
    `AssetCategory`, `Deprecation`
  - 库存: `Part`, `MultiParts`, `PartConsumption`
  - 采购: `PurchaseOrder`, `Vendor`, `Customer`
  - 计量: `Meter`, `Reading`, `Trigger`（读数阈值→自动建单）
  - 组织/多租户: `Company`（租户根）, `OwnUser`, `Role`+`PermissionEntity`, `Team`,
    `Subscription`/`SubscriptionPlan`, `UserInvitation`, `Notification`, `License`
  - 支撑: `Category`, `File`/`Image`, `Currency`, `CustomField`/`FieldConfiguration`
- **功能模块**: 工单、请求(Requests)、预防性维护(PM)、资产、位置、库存、采购单、
  供应商/客户、仪表、团队、角色权限、分析仪表盘、文件、通知、多租户(Company)、订阅、i18n。
- **工单"程序"现状**: `WorkOrder → Task[] → TaskBase`，即**扁平的、带类型的清单**
  （taskType ∈ SUBTASK/INSPECTION/MULTIPLE_CHOICE/METER_READING…），无层级、无版本、无文档结构。
  **这正是 SmartSOP 的 SOP 要替代的部分。**

---

## 3. 目标架构

单一多租户 SaaS = 一个 FastAPI 后端 + 一个 Vue 3 前端 + MySQL，**在 SmartSOP 仓库内扩展**。

```
Smart CMMS
│
├── 平台层 Platform     Tenant(Company) · Auth(JWT) · RBAC(Role/Permission) · Users · Teams · i18n · Audit*
├── SOP 引擎 (已有)      Procedure → Section → Step · 版本 · Word 导入 · PDF 导出   ← 差异化核心
├── 维护域 Maintenance  WorkOrder · Asset · Location · Request · PreventiveMaintenance · Meter
├── 供应域 Supply       Part/Inventory · PurchaseOrder · Vendor · Customer
├── 洞察层 Insight      Analytics/Dashboards · Notifications · Files
└── 商业层 Commercial   Subscription/Plan · 座席&功能门控 · Billing

(* Audit / Attachments / CustomFields 为 SmartSOP 已有，全域复用)
```

**多租户**: 每张领域表新增 `company_id` 实现行级隔离；租户上下文中间件统一对所有查询加作用域。
现有 SOP 表也补充 `company_id`。

---

## 4. SOP × 工单 融合设计（需求 #1 的核心）

用 SmartSOP 的富 SOP **替代** Atlas 的扁平清单（`Task/TaskBase`）：

```
WorkOrder ──引用──> Procedure @ 锁定版本（执行依据）
     │
     └── WorkOrderExecution（工单执行实例）
            └── StepResponse[]（每个 Step：value/status/notes/photos/signature/timestamp/operator）
```

- 创建工单时，计划者挂载一个 SOP Procedure（**锁定到具体版本**，使后续 SOP 修改不影响在途工单）。
- 技师**逐步按 SOP 执行**工单，记录每个 Step 的响应/证据。
- 完成时，填写后的执行记录 + 签名构成工单可审计记录（复用 ReportLab 引擎导出 PDF）。
- Atlas 的 `Task/TaskBase` **不再复刻**——由 SOP 取代。

---

## 5. 路线图：分期子项目

每个阶段是独立的 spec → plan → implement 循环，逐个进行头脑风暴。

| 阶段 | 子项目 | 交付内容 |
|------|--------|----------|
| **0** | **平台基座 Platform Foundation** | 多租户(Company)、认证(注册/登录/JWT/邀请/重置密码)、RBAC(Role/Permission + 内置角色)、用户、团队、i18n(中文默认)、品牌由 SmartSOP 改为 Smart CMMS、为现有 SOP 表回填 `company_id` |
| **1** | **核心维护闭环 (MVP)** | 位置(层级)、资产(层级/分类/状态)、工单(CRUD/状态流转/优先级/指派/到期)、**SOP×工单执行**、工单看板+列表、评论/历史/签名 |
| **2** | **请求与预防性维护** | 请求(Requests，审批→工单)、预防性维护(PM，排程自动生成工单)、仪表/读数/触发器(自动建单)、后台调度器 |
| **3** | **库存与采购** | 备件/库存(库存量/最小库存预警/消耗)、多备件套件、采购单+审批、供应商、客户 |
| **4** | **分析与报表** | 仪表盘：工单合规、成本分析、资产停机/可靠性(MTBF/MTTR)、人工、库存 KPI；报表导出 |
| **5** | **通知与文件** | 站内 + 邮件通知、到期提醒；生产级文件存储(本地/S3 兼容) |
| **6** | **商业化** | 订阅/套餐、座席&功能门控、计费(Stripe)、公司设置、币种、各实体自定义字段 |
| **7** | **移动端 App** | 技师现场执行(离线可用)——按决策后期实现 |

**横切关注点**: i18n、审计(已有)、自定义字段(已有)、工作流/自动化(Triggers)。

---

## 6. 净室重写合规护栏（需求 #3，不可妥协）

每个子项目均须遵守：

- **绝不**复制 Atlas 源码、数据库 DDL、文案字符串、图标、Logo、图片。Atlas 仅作*功能/行为参考*
  （功能与数据关系不受版权保护；具体代码表达受保护）。
- Atlas 代码**绝不**被 import 或链接进构建产物。
- 产品中**不出现** "Atlas" 名称或商标。
- 所有模型/代码均依据领域理解全新编写；独立撰写自己的需求文档。
- 结果：完全自有的专有产品，**无任何 GPL 义务**。

---

## 7. 下一步

1. 保存并提交本路线图规格。
2. 深入头脑风暴 **Phase 0（平台基座）**，产出其设计 spec。
3. 用 writing-plans 技能为 Phase 0 编写实现计划，进入实现。

> 后续每个阶段重复 spec → plan → implement 循环。
