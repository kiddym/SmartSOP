# 配置中心:部署导向总览 Hub + 模块配置聚合页

- 日期:2026-06-08
- 范围:前端 IA 重构(SmartSOP frontend),后端基本不动
- 起点:已落地未提交的「管理→按职责四拆」(本次在其基础上改为按业务对象纵切)

## 1. 背景与动机

当前「管理」大分组把配置按**机制**横切(字段 / 表单 / 工作流 …),但每种机制底下其实各自绑死了不同业务模块,导致两个问题:

- **命名误导**:「字段管理」(`/admin/fields`)底层是 `ProcedureField`(`tb_procedure_field`,带 `show_on_cover` 等 SOP 概念),其实是 **SOP 程序字段**,却起了全局名字。
- **分组不清 + 孤儿入口**:`/admin/request-fields`、`/admin/work-order-fields` 有路由有页面,但**无任何菜单或链接入口**,只能手敲 URL。

更关键的视角:配置有**初次部署**和**日常维护**两种相反的访问模式。

| | 日常维护 | 初次部署 |
|---|---|---|
| 访问模式 | 随机(只调某一项) | 线性(按顺序全配一遍) |
| 需要 | 快速定位 | 顺序 + 不漏配 + 依赖提示 |

纯按模块的平级菜单解决了日常定位,却抹平了部署的依赖线索。本设计用**一个部署导向的总览 Hub** 统一两种需求。

## 2. 部署依赖顺序(IA 编排依据)

部署存在硬依赖,Hub 按此分阶段编排:

```
① 组织基础(公司设置 / 模块显隐开关 / 货币)
   └ 模块开关(show_requests / show_locations / show_meters / show_vendors_customers,
      AppSidebar.hiddenPaths 已读取)决定后续哪些模块需要配 → 部署第 0 步
② 人员权限(角色 → 团队 → 用户)
③ 全局参数(系统设置:审批流 / 版本控制 / 默认风险质量级别等,影响各模块行为)
④ 业务模块配置(仅对已启用模块:SOP / 工单 / 请求 / 资产·库存)
⑤ 自动化(工作流,依赖实体就绪)
⑥ 运维(数据导入 / 文件库 / 审计)
```

## 3. 目标 IA

### 3.1 配置中心总览页(Hub)

- 新路由 `/admin/config`,组件 `ConfigConsoleView.vue`。
- **静态引导**(本期不做实时完成度徽章,零后端成本)。
- 按上述 6 阶段分区块卡片,每块列出配置项入口 + 一句话说明该步做什么。
- 卡片入口指向二级聚合页或既有页面。

总览页结构:

```
配置中心
─────────────────────────
① 组织基础   公司设置·模块开关 / 货币
② 人员权限   角色 / 团队 / 用户
③ 全局参数   系统设置(审批·版本控制)
④ 业务模块   [SOP配置] [工单配置] [请求配置] [自定义字段]
⑤ 自动化     工作流
⑥ 运维       数据导入 / 文件库 / 审计日志
```

### 3.2 模块配置聚合页(二级页,el-tabs)

复用现有 view 组件作为 tab 面板,**不重写业务逻辑**。

| 聚合页 | 路由 | tab 构成 | 复用组件 |
|---|---|---|---|
| SOP 配置 | `/admin/config/sop` | 程序字段 \| 标题字典 | `FieldManageView` + `HeadingRulesView` |
| 工单配置 | `/admin/config/work-order` | 表单字段 \| 自定义字段 \| 工单分类 \| 工时分类 \| 成本分类 | `WorkOrderFieldsView` + `CustomFieldsView`(预筛 work_order)+ 三个分类面板 |
| 请求配置 | `/admin/config/request` | 表单字段 \| 自定义字段 | `RequestFieldsView` + `CustomFieldsView`(预筛 request) |
| 自定义字段 | `/admin/config/custom-fields` | 资产 \| 位置 \| 备件 | `CustomFieldsView`(按实体 tab 预筛) |

**关于「请求」的归属决策**:第一轮范围问答中请求被归入「薄模块合并」侧,但请求有 `fieldConfig(REQUEST)` 这一**自定义字段之外**的独有配置(内置字段显隐/必填)。为保持与工单对称、避免把"表单字段"硬塞进纯自定义字段页,**请求做独立轻聚合页**(表单字段 + 自定义字段)。统一「自定义字段」页只承载没有专属聚合页、且无 fieldConfig 的实体:资产 / 位置 / 备件。

规则:**有专属聚合页的模块,其自定义字段进该页 tab;其余实体进统一「自定义字段」页。**

### 3.3 侧栏(二八划分)

侧栏只保留高频直达 + 一个配置中心入口;低频部署项收进 Hub。

```
管理
 ├ 用户
 ├ 角色
 ├ 团队
 └ 配置中心   → /admin/config(Hub,承载组织基础/全局参数/业务模块/自动化/运维/审计的完整引导)
```

人员权限既在侧栏直达(高频),又在 Hub ② 列出(部署引导)——双入口不冲突。

## 4. 技术实现要点

### 4.1 CustomFieldsView 支持实体预筛

`CustomFieldsView` 现为「单页 + 实体下拉筛选」。新增可选 prop / route 参数 `lockedEntity`:传入时隐藏实体选择器、锁定单实体(列表查询与新建表单都固定该 entity)。聚合页 tab 通过该入参复用同一组件,互不串数据。

### 4.2 分类管理 Dialog 抽出为可复用面板

`WorkOrderCategoryManageDialog` / `TimeCategoryManageDialog` / `CostCategoryManageDialog` 当前是工单业务流里的弹窗。把其**列表管理主体**抽成无壳面板组件(如 `*ManagePanel.vue`),供:

- 工单配置聚合页 tab 内嵌;
- 原 Dialog 继续 import 该面板(业务页保留快捷入口,行为不变)。

抽取保持 API 调用(`api/workOrderCategories`、`api/timeCategories`、`api/costCategories`)不变。

### 4.3 聚合页骨架

每个聚合页是薄壳:`el-tabs` + 页标题,tab 内容 = `<component>` 渲染复用组件,`tab` 名经 route query(如 `?tab=custom-fields`)驱动,便于 redirect 落到指定 tab。

### 4.4 路由与 redirect(不破坏书签)

- 新增:`/admin/config`、`/admin/config/sop`、`/admin/config/work-order`、`/admin/config/request`、`/admin/config/custom-fields`。
- 旧路由保留为 redirect:
  - `/admin/fields` → `/admin/config/sop?tab=fields`
  - `/admin/heading-rules` → `/admin/config/sop?tab=heading-rules`
  - `/admin/work-order-fields` → `/admin/config/work-order?tab=form-fields`
  - `/admin/request-fields` → `/admin/config/request?tab=form-fields`
  - `/admin/custom-fields` → `/admin/config/custom-fields`
- 既有 `/settings/*`、`/platform/*` 旧别名 redirect 全部保留不动。
- `AppSidebar.activeMenu` 增加 `/admin/config*` 的高亮归并。

## 5. 范围与非目标

**做**:总览 Hub、4 个聚合页、CustomFieldsView 预筛、3 个分类面板抽取、菜单与路由重排、旧路由 redirect。

**不做(YAGNI)**:

- 实时完成度徽章(本期静态引导)。
- 强制安装向导 wizard。
- 后端新端点 / 模型变更(全部复用现有 API)。
- 任何与本目标无关的重构。

## 6. 验证

- `npm run typecheck` + `npm run lint` 绿。
- 前端单测全绿(`npm run test`)。
- 运行态(`running-smartsop-dev` skill)人工走查:Hub 六区块入口可达;各聚合页 tab 切换、CRUD 正常;旧 URL redirect 命中正确 tab;侧栏「配置中心」高亮;模块开关关闭后对应模块配置入口随 `hiddenPaths` 隐藏。

## 7. 风险

- **分类 Dialog 抽取**回归风险:三个弹窗在业务页仍被使用,抽面板后需确保 Dialog 与聚合页两处都正常。以现有单测 + 运行态走查兜底。
- **CustomFieldsView 改造**:`lockedEntity` 为可选入参,不破坏 `/admin/config/custom-fields` 之外的既有用法;但需回归原页面行为。
