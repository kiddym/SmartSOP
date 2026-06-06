# 业务实体动态自定义字段（CustomField）设计

> 日期：2026-06-06 ｜ 状态：设计待实现 ｜ 关联：净室重写基线、C1 FormFieldConfig、SOP ProcedureField

## 1. 背景与目标

C1 已交付 `FormFieldConfig`——仅对**预定义字段**做显隐/必填配置。本设计补齐 Atlas CustomField 的核心能力：**管理员为业务实体动态新增任意自定义字段**。

SmartSOP 已有一套完整的动态字段系统，但仅服务 SOP 程序：
- 字段定义：`ProcedureField` 表（per company，含 `key`(不可改)/`field_type`/`options`/`validation_rules`/`required`/`default_value`/`sort_order`/`status`）。
- 字段值：宿主实体上的 JSON 列 `Procedure.custom_values`（按 `key` 存）。
- 值校验：`app/services/field_service.py` 的 `validate_values()` / `_validate_one()`。

本设计**复用该「定义表 + 宿主 JSON 值列 + 共享校验」心智模型**，用一张多态 `CustomFieldDef` 表服务业务实体，与 SOP 系统解耦（方案 A）。

### 需求边界（已澄清）
- **覆盖实体**：`work_order` / `asset` / `request` / `location` / `part`（核心主数据 5 实体）。
- **值查询性**：仅录入 + 展示，**不需筛选/搜索/分析聚合** → 值用宿主 JSON 列存储。
- **字段类型**：复用现有基础类型集 `text / number / date / select / multi_select / checkbox / textarea`，**不引入跨实体引用类型**。
- **净室红线**：仅功能对账、全新原创，不复制 Atlas 代码/DDL/命名。

### 非目标（YAGNI / 留后续）
- 自定义字段值的筛选、搜索、报表聚合。
- 引用类字段（user/asset 引用）、currency/boolean 等扩展类型。
- 删除字段后对宿主 JSON 的主动清理（孤儿 key 读取时忽略即可）。
- 存量旧实体的默认值回填。

## 2. 架构方案（方案 A）

**新建独立 `CustomFieldDef` 多态定义表 + 各宿主实体 `custom_values` JSON 值列 + 抽取共享校验模块。**

- 与已上线、已测试的 SOP `ProcedureField` 完全解耦，业务自定义字段独立演进；边界清晰、回归风险低。
- 唯一重复点（字段类型/值校验逻辑）通过抽取共享模块 `field_validation.py` 消化，SOP 与业务侧共用。
- 借用成熟的 `ENTITY_REGISTRY`（附件多态注册表）做 `entity_type` → 宿主模型/权限解析的同名键集合。

> 已否决：方案 B（泛化 ProcedureField，触动已上线 SOP 系统、耦合 SOP 与业务关注点、回归风险高）；方案 C（每实体一张定义表，5 套近乎相同表+CRUD，重复严重）。

## 3. 数据模型

### 3.1 定义表 `tb_custom_field_def`
`UUIDMixin + TimestampMixin + SoftDeleteMixin + TenantMixin`，列：

| 列 | 类型 | 说明 |
|---|---|---|
| `entity_type` | String(32) | `work_order/asset/request/location/part`，受控（ENTITY_REGISTRY 键集） |
| `key` | String(100) | 编程键 `^[a-z][a-z0-9_]*$`；创建后**不可改** |
| `name` | String(100) | 显示名 |
| `field_type` | String(20) | `text/number/date/select/multi_select/checkbox/textarea` |
| `description` | Text | 默认 '' |
| `required` | Bool | 默认 False |
| `default_value` | JSON | 可空 |
| `options` | JSON | select/multi_select 的选项列表，默认 [] |
| `validation_rules` | JSON | 标准 JSON Schema 子集，默认 {} |
| `sort_order` | Integer | 默认 0 |
| `status` | String(20) | `active`/`archived`，默认 active |

约束：`UniqueConstraint(company_id, entity_type, key)`；索引 `company_id`、`entity_type`。

### 3.2 宿主值列
给 5 张宿主表各加 `custom_values` JSON 列（默认 `{}`）：`tb_work_order` / `tb_asset` / `tb_request` / `tb_location` / `tb_part`。按 `key` 存值，与 `Procedure.custom_values` 一致。

### 3.3 迁移
一个迁移（down_revision = 当前单 head）：
- `create_table tb_custom_field_def`（唯一约束 + 两索引，`created_at/updated_at` 用 `DATETIME6`）。
- `batch_alter_table` 给 5 张宿主表各加 `custom_values` JSON 列（default `{}`，server_default 表达式避免 MySQL TEXT 字面默认雷区——JSON 列按既有 JSON 列迁移惯例处理）。
- downgrade 反向（SQLite 显式删索引再 DROP 表、删 5 列）。
- 验证单 head + 重放 upgrade/downgrade/upgrade。

## 4. 字段定义管理 API

路由 `app/routers/custom_fields.py`，前缀 `/api/v1/custom-fields`，service `app/services/custom_field_service.py`：

| 端点 | 权限 | 说明 |
|---|---|---|
| `GET /custom-fields?entity_type=&include_archived=` | 任意认证 | 列定义（默认仅 active，按 sort_order） |
| `POST /custom-fields` | `company.settings` | 新建；校验 entity_type∈注册集、key 格式与唯一 |
| `PATCH /custom-fields/{id}` | `company.settings` | 改定义（`key`/`entity_type` 不可改，其余可改） |
| `PATCH /custom-fields/{id}/archive` ｜ `/restore` | `company.settings` | 归档/恢复 |
| `DELETE /custom-fields/{id}` | `company.settings` | 软删 |
| `POST /custom-fields/reorder` | `company.settings` | 批量调 sort_order |

- `entity_type` 未知 → 422；`key` 非法格式 → 422；`(company,entity,key)` 冲突 → 409/422。
- 跨租户 get_or_404；多租户自动隔离。
- main.py 注册 router；不新增权限码（复用 `company.settings`）。

## 5. 值读写集成

### 5.1 写入
- 5 实体的 Create/Update schema 加可选 `custom_values: dict[str, Any]`。
- 各实体 service 落库前调 `custom_field_service.validate_values(db, entity_type, custom_values)`：
  - 按该 entity_type 的 **active** 定义逐项校验：类型符合、必填非空、select/multi_select 值∈options、JSON Schema 规则。
  - **未知 key（无对应定义，连 archived 都没有）→ 拒绝 422**（防脏数据）。
- update 语义：`custom_values=None` 不动；给 dict 则**按 key 合并**进宿主 `custom_values`（payload 中的 key 覆盖、未出现的 key 保留）。
  - 选用 key 级合并而非整体替换的原因：录入表单只渲染 active 字段、提交时只带 active 字段值；若整体替换会把 archived 字段的已存值（表单不渲染、故不在 payload）误删。合并下，active 字段（含清空=空串）总在 payload 被覆盖，archived 字段值因不在 payload 而天然保留——与 §7「归档字段值只读保留」一致。

### 5.2 读取
- 5 实体 Read schema 暴露 `custom_values: dict`。
- 前端按 `GET /custom-fields?entity_type=` 定义渲染；孤儿 key（无对应定义）不展示。

### 5.3 共享校验模块
把 `field_service.py` 的 `_validate_one` / 类型校验 / `_is_empty` 抽到 `app/services/field_validation.py`，参数化"按哪批字段定义校验"。`field_service`(SOP) 与 `custom_field_service`(业务) 共用。**此抽取不改变 SOP 现有行为**，SOP 既有测试须保持绿。

## 6. 前端

### 6.1 定义管理页
- `src/views/settings/CustomFieldsView.vue` + 路由 `/admin/custom-fields`（`company.settings` 门控写）+ 侧栏「管理/系统配置」组入口。
- 顶部实体类型切换；字段定义列表（名称/key/类型/必填/状态）+ 新建/编辑对话框（编辑态 `key` 只读；select 类显示选项编辑器）+ 归档/恢复/删除/拖拽排序。
- `src/api/customFields.ts` + 类型。

### 6.2 可复用 `CustomFieldsSection.vue`
- 入参 `entityType` + `v-model:values`（绑宿主 `custom_values`）。
- 拉 active 定义，按 `field_type` 渲染控件（text→input、number→number、date→date-picker、select→select、multi_select/checkbox→多选、textarea→textarea），必填校验。
- 接入点：5 实体的创建/编辑表单各挂一个独立"自定义字段"分区（与内置字段、C1 显隐配置正交）；详情页（F1/F2/F3 等）加只读展示区。
- 加载失败/无定义时该区不显示，不阻断主表单。

### 6.3 前端测试
管理页 CRUD；CustomFieldsSection 各类型渲染+必填校验+提交携带 values。

## 7. 权限、多租户、边界

- **权限**：定义管理 = `company.settings`；值写入跟随宿主 `*.edit`/`*.create`（随实体一起写）；读取 = 任意认证。
- **多租户**：定义表挂 TenantMixin 自动隔离；`custom_values` 在宿主行内随宿主租户；校验只查当前 company 定义。
- **key 不可改**：建后锁定，保证已存值不失联。
- **归档**：退出录入表单，详情仍只读展示已存值；其值因 update 走 key 级合并（不在 payload 即保留）而不被误删。
- **删除**：定义软删后孤儿 key 读取忽略，不主动清理宿主 JSON（留后续清理任务）。
- **必填**：仅对 active 字段、且提交了 custom_values 时校验；不强制回填存量。
- **default_value**：前端新建预填；后端不强制注入。

## 8. 测试策略

- 后端：定义 CRUD + key 不可改 + per company×entity 唯一 + 跨租户隔离；值校验（类型不符/必填缺失/未知 key 422/select 非法选项）；归档后退出录入但读保留；删除后孤儿 key 忽略；共享校验模块单测；5 实体各一条"带 custom_values 建/改/读回"。
- 门禁：迁移单 head 可重放、`import app.main`、ruff check + ruff format --check + mypy、既有 SOP 字段测试与 5 实体既有测试不破；前端 vue-tsc + eslint + vitest。

## 9. 实现顺序（增量）

1. 抽取共享校验模块 `field_validation.py`（不改 SOP 行为，回归保绿）。
2. `tb_custom_field_def` 表 + 迁移（含 5 宿主列）+ 管理 API。
3. 5 实体 schema/service 接 `custom_values`（写时共享校验、整体替换、未知 key 422）。
4. 前端定义管理页 `CustomFieldsView` + api。
5. `CustomFieldsSection` + 5 实体表单接入 + 详情只读展示。

每步独立 commit、门禁全绿。
