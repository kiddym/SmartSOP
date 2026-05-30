# Phase 1A：基础域（Location / Asset / Team）设计

- **日期**: 2026-05-30
- **状态**: 已批准（设计）
- **上游**: [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) · [功能对标矩阵](2026-05-30-feature-parity-matrix.md) · [Phase 0 设计](2026-05-30-phase-0-platform-foundation-design.md)
- **作者**: brainstorming 协作产出

---

## 1. 目标与范围

为 Smart CMMS 维护域建立"被维护对象"基座：**位置层级、资产（分类/层级/状态/停机记录/扫码标识）、团队**，全部作为一等多租户实体。这是 Phase 1B 工单闭环的前置依赖（工单绑定资产/位置、指派给用户/团队）。

本期遵循[净室重写护栏](2026-05-30-smart-cmms-master-roadmap-design.md#6-净室重写合规护栏需求-3不可妥协)：Atlas 仅作行为参考，绝不复制其源码/DDL/文案/品牌。

复用 Phase 0 多租户基座（见 [tenant 架构](2026-05-30-phase-0-platform-foundation-design.md)）：`TenantMixin`、`TenantContextMiddleware`（按 bearer token 为整请求设租户上下文，隔离 fail-closed）、`_ensure_same_tenant` 兜底、`require_permission`、软删 helper。

### 1.1 本期交付（In）

- **Location**：CRUD + 自引用树（不限深、仅防环）、地理坐标/地址、customId（`L%06d`）、关联 assignedTo(用户)/teams、子位置/根位置/mini 下拉查询
- **Asset**：CRUD + 自引用树、完整字段、customId（`A%06d`）、barcode/nfcId（租户内唯一 + 按码查询）、状态机（7 值→UP/DOWN）、绑定 location、关联 primaryUser/assignedTo(多)/teams、子/根/mini 查询、按 location/category/status/parent 过滤
- **AssetCategory**：独立 CRUD 表
- **AssetDowntime**：手动登记停机时段（start/end/原因）+ 资产当前状态字段；**不做**树传播（→ 1B/Phase 4）
- **Team**：CRUD + team↔user 成员（M:N）
- **通用每租户自增序列 Sequence**：并发安全，服务 Asset/Location customId，并供后续库存/采购/工单复用
- 新权限点 `location.* / asset.* / asset_category.* / team.*` 入 registry；内置 4 角色补默认集
- 全部走 Phase 0 `TenantContextMiddleware` 自动作用域 + `_ensure_same_tenant` 兜底
- 一个 Alembic 增量迁移（沿用 Phase 0 的 dialect 分支处理 SQLite 无法 ALTER ADD FK）

### 1.2 明确不做（Out，部分预留）

- 停机树传播（向上传祖先/向下传后代）→ 1B/Phase 4
- 折旧 Deprecation、平面图 FloorPlan → 后期
- vendors / customers / parts / files 关联（对端表在 Phase 3 / 文件阶段）
- WorkOrder / 请求 / PM / 计量 → 1B / Phase 2
- 前端业务 UI（本期后端 API 优先；UI 作为紧随其后的小周期）

---

## 2. 数据模型

`*` = `TenantMixin` 提供的 NOT NULL `company_id`（行级隔离）。全部 UUID 主键、`tb_` 前缀、软删（`SoftDeleteMixin`：`is_active` / `deleted_at`）。M:N 关联表同样带 `company_id*`，使其成为 `TenantScoped`，作用域统一。

### 2.1 Sequence（通用每租户自增计数器）

```
Sequence
    id, company_id*, scope(str, 如 "asset"/"location"), next_val(int, 默认 1)
    约束: UNIQUE(company_id, scope)
```

- 取号服务 `sequence_service.next_value(db, scope) -> int`：在事务内对该 (company_id, scope) 行加锁原子自增。
  - MySQL：`SELECT ... FOR UPDATE` 行锁后 `next_val += 1`。
  - SQLite（测试）：连接串行化，普通 UPDATE 即原子。
  - 行不存在则按当前租户上下文创建（next_val 从 1 起）。
- customId 格式由调用方决定：asset → `f"A{n:06d}"`，location → `f"L{n:06d}"`。
- 后续阶段（库存/采购/工单 customId）直接复用本机制，仅新增 scope。

### 2.2 Location

```
Location
    id, company_id*, custom_id(L000001), name, description,
    parent_id → Location(自引用, 不限深, 防环), address, longitude(float|null), latitude(float|null),
    created_at, updated_at, is_active, deleted_at
关联表:
    tb_location_user  (company_id*, location_id, user_id)   -- assignedTo/workers
    tb_location_team  (company_id*, location_id, team_id)
```

### 2.3 AssetCategory

```
AssetCategory
    id, company_id*, name, created_at, updated_at, is_active, deleted_at
    约束: UNIQUE(company_id, name)
```

### 2.4 Asset

```
Asset
    id, company_id*, custom_id(A000001), name, description,
    parent_id → Asset(自引用, 不限深, 防环),
    location_id → Location (nullable, FK RESTRICT),
    category_id → AssetCategory (nullable, FK SET NULL),
    status(AssetStatus 枚举, 见 2.6),
    serial_number, model, manufacturer, power,
    warranty_expiration_date(date|null), in_service_date(date|null), acquisition_cost(numeric|null),
    barcode(str|null), nfc_id(str|null),
    primary_user_id → User (nullable, FK SET NULL),
    created_at, updated_at, is_active, deleted_at
    约束: barcode 非空时租户内唯一; nfc_id 非空时租户内唯一
关联表:
    tb_asset_user  (company_id*, asset_id, user_id)   -- assignedTo(多)
    tb_asset_team  (company_id*, asset_id, team_id)
```

- **barcode/nfc 部分唯一**：沿用 SmartSOP 已有的"非空时唯一"套路（MySQL 生成列 partial-unique 或应用层校验）；跨租户允许同码。
- `acquisition_cost` 用 `Numeric`（金额，避免浮点）。

### 2.5 AssetDowntime

```
AssetDowntime
    id, company_id*, asset_id → Asset(FK RESTRICT),
    started_at, ended_at(datetime|null = 进行中),
    reason(str), downtime_type(str, 默认 "manual"; 预留 "workorder" 等),
    created_at, updated_at
```

- 无树传播。`ended_at` 为空 = 当前停机中。
- 停机时段为审计/可靠性数据：只新增 + 闭合（填 `ended_at`），不软删。

### 2.6 Team 与 AssetStatus

```
Team
    id, company_id*, name, description, created_at, updated_at, is_active, deleted_at
    约束: UNIQUE(company_id, name)
关联表:
    tb_team_user  (company_id*, team_id, user_id)   -- 成员
```

**AssetStatus 枚举（7 值，映射 UP/DOWN，供 Phase 4 可用率）**：

| 值 | UP/DOWN |
|---|---|
| `OPERATIONAL` | UP |
| `STANDBY` | UP |
| `MODERNIZATION` | DOWN |
| `INSPECTION_SCHEDULED` | UP |
| `COMMISSIONING` | UP |
| `EMERGENCY_SHUTDOWN` | DOWN |
| `DOWN` | DOWN |

- 在 `asset_status.py`（或模型旁）提供 `UP_STATUSES` / `DOWN_STATUSES` 常量集合，供后续可用率计算复用。默认状态 `OPERATIONAL`。

---

## 3. API 面

全部 `/api/v1` 前缀，认证 + 权限点保护。DELETE = 软删。

```
位置  GET/POST           /api/v1/locations            (列表支持 parent 过滤)
      GET/PATCH/DELETE   /api/v1/locations/{id}
      GET                /api/v1/locations/{id}/children
      GET                /api/v1/locations/mini        (下拉: id+name+custom_id)
资产  GET/POST           /api/v1/assets               (列表支持 location/category/status/parent 过滤)
      GET/PATCH/DELETE   /api/v1/assets/{id}
      GET                /api/v1/assets/{id}/children
      GET                /api/v1/assets/mini
      GET                /api/v1/assets/by-barcode/{code}
      GET                /api/v1/assets/by-nfc/{nfc}
      POST               /api/v1/assets/{id}/downtimes        (登记停机)
      PATCH              /api/v1/assets/{id}/downtimes/{did}  (闭合 ended_at)
      GET                /api/v1/assets/{id}/downtimes
分类  GET/POST/PATCH/DELETE  /api/v1/asset-categories
团队  GET/POST/PATCH/DELETE  /api/v1/teams
      PUT                /api/v1/teams/{id}/members           (设成员用户集)
```

**删除/引用策略**：
- 树节点有子节点时删除 → `bad_request`（与 SOP Folder 一致）。
- 资产挂在位置上、位置被资产引用 → FK RESTRICT，删除被拒并提示。
- 跨租户访问任何 `{id}` → `_ensure_same_tenant` → 404。

---

## 4. RBAC 权限点

入 `app/permissions.py` registry：

```
location.view / location.create / location.edit / location.delete
asset.view / asset.create / asset.edit / asset.delete
asset_category.view / asset_category.manage
team.view / team.manage
```

内置角色默认集补齐：

| 角色 | 1A 默认权限 |
|---|---|
| super_admin | 全部（通配，自动包含新点） |
| admin | 全部 1A 权限 |
| technician | `*.view` + `asset.edit`（现场改资产状态/登记停机） |
| viewer | 仅 `*.view` |

> super_admin 是通配，无需逐点补。其余三角色显式补 code 列表。

---

## 5. 架构与文件（沿 Phase 0 扁平布局）

```
backend/app/
  models/      sequence.py location.py asset.py asset_category.py asset_downtime.py team.py
               (+ 关联表，可置于各自模型文件内或 associations.py)
               asset_status.py (枚举 + UP/DOWN 常量)
  schemas/     location.py asset.py asset_category.py team.py
  services/    sequence_service.py location_service.py asset_service.py
               asset_category_service.py team_service.py
  routers/     locations.py assets.py asset_categories.py teams.py   (→ main.py 挂载)
  permissions.py   (扩充)
  alembic/versions/<rev>_phase1a_base_domain.py
```

**关键复用**：`TenantMixin`、`TenantContextMiddleware`、`_ensure_same_tenant`、`require_permission`、`SoftDeleteMixin`、SOP Folder 树/删除模式、`FolderSequence` 取号模式。

**迁移**：沿用 Phase 0 dialect 分支——MySQL 建真 FK，SQLite（dev/test）建普通可空列（SQLite 不支持 ALTER ADD FK）。新建表的 FK 在 `create_table` 内对两种方言均可。

---

## 6. 测试重点（pytest，沿用 conftest 与 client/db fixtures）

- **跨租户隔离（最高优先，e2e）**：A 租户读/改/删 B 的资产/位置/团队/分类/停机 → 404；列表不含他租户行。
- **Sequence 并发安全 + 每租户独立**：两租户各自从 1 起；同租户连续取号不重复；并发取号无重号。
- **树**：防环（设自身/后代为父 → 拒绝）、children 查询正确、有子节点删除被拒。
- **barcode/nfc**：租户内唯一冲突报错、按码查询命中、跨租户同码允许。
- **状态机 + 停机**：登记停机、闭合 ended_at、UP/DOWN 归类正确。
- **RBAC**：technician 能 `asset.edit` 不能 `asset.delete`（403）；viewer 只读；无 token 401。
- **customId 格式**：A000001 / L000001。
- **全量回归**：不破坏 Phase 0 与 SOP 既有测试。

---

## 7. 净室合规复核

- 全新数据模型，依据领域理解编写，未参照 Atlas 任何 DDL/源码。
- 不含 "Atlas" 名称、商标、文案、资源。
- 资产/位置树、状态机、停机记录、序列号为通用工程/领域模式，非受版权保护的具体表达。

---

## 8. 下一步

1. 提交本 spec。
2. 用 writing-plans 技能为 Phase 1A 编写实现计划（TDD，bite-sized）。
3. 进入实现（subagent-driven，**串行**派发实现子代理——见教训记忆）。
4. 之后 Phase 1B（工单闭环 + SOP×工单执行）再走 spec→plan→implement。
