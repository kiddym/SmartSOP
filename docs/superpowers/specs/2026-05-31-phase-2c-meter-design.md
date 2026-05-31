# Phase 2C 计量（Meter）设计 spec

> Phase 2 拆为三个独立周期（2A Request / 2B PreventiveMaintenance / 2C Meter），各自走完整 spec→plan→implement。本文是 **2C**，承接 [2B PM](2026-05-31-phase-2b-pm-design.md)。

## 1. 目标与范围

**目标**：实现事件驱动的「读数越过阈值 → 自动生成工单」，作为 Request/PM 之后的第三种「触发源→生成工单」，补齐计量模块核心。区别于 PM 的时间排程，本模块由**提交读数**事件同步驱动。

### 纳入范围
- `Meter` 仪表：挂资产（asset_id），含 unit（单位）、update_frequency_days（期望抄表节奏，天，仅元数据）、name、可选 location。
- `MeterReading` 读数：挂 meter，记 value + reading_at + recorded_by。
- `WorkOrderMeterTrigger` 触发器：挂 meter，含 comparator(LESS_THAN/MORE_THAN) + threshold + `is_armed` + 全套工单预设（title/description/priority/primary_user/assignee_ids/team_ids/procedure_id）。
- 提交读数同步评估该 meter 全部启用 trigger；边沿命中（armed→满足）生单 + 解除武装；读数回落未满足则重新武装。
- 复用 `work_order_service.create_work_order` + `work_order_execution_service.attach_procedure` 生单。
- RBAC：meter.{view,create,edit,delete} + reading.{view,create}。

### 不纳入范围（明确延后）
- MeterCategory 仪表分类、商业 METER 套餐门控。
- update_frequency_days 的节奏校验/逾期查询（仅存元数据）。
- **通知**：Atlas 原行为含「生单 + 通知」，本系统尚无通知子系统，本期只做生单 + 既有 WO 活动记录，通知待通知模块落地后接入。
- SOP 抄表型步骤回写 Reading（属 SOP 执行集成，另期）。
- 读数的修改/删除（append-only，审计完整性；更正属后期）。

### 沿用既有不变约束
clean-room、零 GPL 风险（输出不出现 "Atlas" 字样、不抄源码/DDL/文案）、多租户隔离（中间件 + ORM 事件）、`tb_` 前缀、UUID 字符串主键、软删 `is_active`/`deleted_at`、每租户 Sequence 编号、复用 `WorkOrderPriority` 枚举。

## 2. 数据模型

方案：与 PM 同构，Trigger 即工单模板。共 **5 张表**（均 `tb_` 前缀、UUID 主键、TenantMixin 盖租户章）。

### ① `tb_meter` 仪表（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| custom_id | String(20) | 每租户 Sequence，前缀 `MTR`（如 MTR000001）|
| name | String(300) | 仪表名 |
| unit | String(50) | 单位（hours/℃/km…）|
| update_frequency_days | Integer, nullable | 期望抄表节奏（天），仅元数据 |
| asset_id | String(36) FK tb_asset RESTRICT, nullable, index | 所挂资产 |
| location_id | String(36) FK tb_location RESTRICT, nullable, index | 可选位置 |

### ② `tb_meter_reading` 读数（仅 Timestamp + Tenant，**append-only 不软删**）
| 字段 | 类型 | 说明 |
|---|---|---|
| meter_id | String(36) FK tb_meter CASCADE, index | |
| value | Numeric(18,4) | 读数值（Numeric 避免浮点漂移影响阈值比较）|
| reading_at | DATETIME6, default utcnow | 抄表时刻（可由客户端传，默认当前）|
| recorded_by_user_id | String(36), nullable | 抄表人 |

### ③ `tb_meter_trigger` 触发器（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| meter_id | String(36) FK tb_meter CASCADE, index | |
| name | String(300) | 如「高温告警」|
| comparator | Enum `MeterComparator`(LESS_THAN/MORE_THAN) | 严格不等：value >/< threshold 才满足，相等不算 |
| threshold | Numeric(18,4) | 阈值 |
| is_armed | Boolean, nullable=False, default True, server_default "1" | 武装态（边沿去重核心）|
| is_enabled | Boolean, nullable=False, default True, server_default "1" | 可启停 |
| priority | Enum WorkOrderPriority, default NONE | 生单优先级预设 |
| title | String(300), nullable=False | 生单标题预设 |
| description | Text, default "" | 生单描述预设 |
| primary_user_id | String(36) FK tb_user SET NULL, nullable, index | |
| procedure_id | String(36) 弱引用（无 FK）, nullable, index | SOP 预设 |
| last_triggered_at | DATETIME6, nullable | |
| last_work_order_id | String(36), nullable | |

### ④ `tb_meter_trigger_assignee`（+ Tenant，唯一约束 uq_meter_trigger_assignee）
trigger_id (FK tb_meter_trigger CASCADE) + user_id (FK tb_user CASCADE)，同 PMAssignee。

### ⑤ `tb_meter_trigger_team`（+ Tenant，唯一约束 uq_meter_trigger_team）
trigger_id (FK tb_meter_trigger CASCADE) + team_id (FK tb_team CASCADE)，同 PMTeam。

### 新增枚举与 Sequence
- `MeterComparator(str, Enum)`：`LESS_THAN = "LESS_THAN"` / `MORE_THAN = "MORE_THAN"`。
- 新增 Sequence kind `"meter"`（仅 Meter 有 custom_id；trigger/reading 无）。

### 取舍：不建独立活动表
PM 当时有 `PMActivity` 时间线表。Meter 不建独立活动表（YAGNI）——读数表本身即事件流，触发器的 `last_triggered_at`/`last_work_order_id` 记录最近一次发火，生成的工单又有自己的 WO_GENERATED 活动。

## 3. 触发语义与边沿评估算法

PM「锥摆」的对应物——边沿触发状态机。

### 条件满足（严格不等）
```
MORE_THAN:  value > threshold   →  满足
LESS_THAN:  value < threshold   →  满足
（相等不算满足）
```

### 边沿状态机（纯函数，逐 trigger 评估）
```
met = _condition_met(comparator, value, threshold)
action =
    FIRE    if met and is_armed              # 跨入满足 → 生单 + 解除武装
    REARM   if (not met) and (not is_armed)  # 回落未满足 → 重新武装
    NOOP    otherwise                        # 持续满足(已发火,抑制) / 持续未满足
```
- `FIRE` → 生成工单、`is_armed=False`、记 `last_triggered_at`/`last_work_order_id`。
- `REARM` → `is_armed=True`，不生单。
- 新建 trigger 默认 `is_armed=True`，故首条满足读数即发火。
- 一条读数评估该 meter 的**所有** trigger（含 is_active & is_enabled）；可 0..N 次发火（不同阈值的多个 trigger 可同时满足）。disabled / 软删的 trigger 跳过（既不发火也不改武装态）。

### 生单细节
- 复用 `create_work_order`（内部 commit）+ `attach_procedure`，复制 trigger 全套预设。
- WO `due_date = None`（阈值突破是反应式工单，无内在截止日）。
- `last_triggered_at = reading.reading_at`（事件时刻，非 wall-clock）。

### 事务
提交读数处理器内——插入 reading → flush → 顺序评估各 trigger → 发火者调 `create_work_order`（随之 commit）+ 更新 trigger 字段 → 末尾 commit 落地 reading 与 trigger 状态。单条读数通常仅 0–1 次发火，顺序评估即可；发火异常以 500 上抛（罕见）。

### 编辑再武装规则
编辑 trigger 的 **threshold 或 comparator** 时 → 重置 `is_armed=True`，使其对未来读数全新评估（PM「改 start_date 重置 next_due」的对应物）；仅改预设（标题/指派/SOP/优先级）不动武装态。

## 4. Service 分层与 API

### Service 拆两文件

**`app/services/meter_trigger_service.py`**（触发器 + 评估引擎）
- 纯函数：`_condition_met(comparator, value, threshold) -> bool`、`_decide(is_armed, met) -> "FIRE"|"REARM"|"NOOP"`
- 关联查询：`assignee_ids(db, trigger_id)`、`team_ids(db, trigger_id)`
- CRUD：`create_trigger` / `list_triggers(db, meter_id)` / `get_trigger` / `update_trigger`（含 threshold/comparator 改即 `is_armed=True`）/ `delete_trigger`（软删）/ `enable_trigger` / `disable_trigger`
- `generate_from_trigger(db, trigger, *, reading, actor_user_id) -> WorkOrder`：复制预设 → `create_work_order`(+`attach_procedure`) → 置 `last_triggered_at/last_work_order_id`、`is_armed=False`

**`app/services/meter_service.py`**（仪表 + 读数 + 编排）
- Meter CRUD：`create_meter`（Sequence `MTR`）/ `list_meters(db, asset_id?, location_id?)` / `get_meter` / `update_meter` / `delete_meter`（软删）
- `submit_reading(db, meter, payload, company_id, actor_user_id) -> tuple[MeterReading, list[WorkOrder]]`：插入 reading → flush → 取该 meter 全部启用 trigger（按 created_at,id 序）→ 逐个 `_condition_met`+`_decide`，FIRE 调 `generate_from_trigger`、REARM 置武装 → commit。返回读数 + 生成的工单列表。
- `list_readings(db, meter_id) -> list[MeterReading]`

### API `app/routers/meters.py`（挂 `/api/v1/meters`）

| 方法 路径 | 权限 |
|---|---|
| GET `/meters`（filter asset_id/location_id） | meter.view |
| POST `/meters` | meter.create |
| GET `/meters/{id}` | meter.view |
| PATCH `/meters/{id}` | meter.edit |
| DELETE `/meters/{id}` | meter.delete |
| GET `/meters/{id}/readings` | reading.view |
| POST `/meters/{id}/readings` → 评估触发器，返回 `{reading, generated_work_order_ids}` | reading.create |
| GET `/meters/{id}/triggers` | meter.view |
| POST `/meters/{id}/triggers` | meter.create |
| GET `/meters/{id}/triggers/{tid}` | meter.view |
| PATCH `/meters/{id}/triggers/{tid}` | meter.edit |
| DELETE `/meters/{id}/triggers/{tid}` | meter.delete |
| POST `/meters/{id}/triggers/{tid}/enable` · `/disable` | meter.edit |

- 触发器嵌套在 meter 下；租户校验经 `meter.company_id == current_user.company_id` → 404（trigger 再校验归属该 meter）。
- 无手动「立即发火」端点（trigger 由读数驱动，YAGNI）。

### Schemas `app/schemas/meter.py`
- `MeterCreate` / `MeterUpdate`（全可选）/ `MeterRead`
- `MeterReadingCreate`（value 必填、reading_at 可选）/ `MeterReadingRead`
- `TriggerCreate` / `TriggerUpdate`（全可选）/ `TriggerRead`（含 assignee_ids/team_ids；is_armed、last_triggered_at、last_work_order_id 只读，由 service 维护，不可写）
- `ReadingResult{reading: MeterReadingRead, generated_work_order_ids: list[str]}`

`TriggerRead.assignee_ids`/`team_ids` 非 ORM 属性，由 service/router 在 model_validate 后填充（同 PM 的 `_read`）。

## 5. RBAC 权限

新增 6 个权限码，分两组（同 2B 的 `_REQUEST`/`_PREVENTIVE_MAINTENANCE` 模式）：
```python
METER_VIEW   = "meter.view"
METER_CREATE = "meter.create"
METER_EDIT   = "meter.edit"
METER_DELETE = "meter.delete"
READING_VIEW   = "reading.view"
READING_CREATE = "reading.create"

_METER   = [METER_VIEW, METER_CREATE, METER_EDIT, METER_DELETE]
_READING = [READING_VIEW, READING_CREATE]
ALL_PERMISSIONS = _PLATFORM + _BASE_DOMAIN + _WORKORDER + _REQUEST + _PREVENTIVE_MAINTENANCE + _METER + _READING
```

角色默认：
- super_admin / admin：自动含全部 6 码。
- **technician**：`meter.view` + `reading.view` + `reading.create`（看仪表、提交读数；不能改仪表/触发器）。
- viewer：自动经 `.endswith(".view")` 过滤含 `meter.view` + `reading.view`。
- requester：不变。

契约测试：新增 `tests/test_permissions_phase2c.py`（照 2B 惯例），断言 6 码注册、admin/super_admin 全含、technician 三码、viewer 两个 .view、requester 不变。

## 6. 迁移 · 接线 · 测试策略

**迁移** `backend/alembic/versions/20260531_0006_phase2c_meter.py`（`revision="phase2c_meter"`, `down_revision="phase2b_pm"`）：手写 `_ts/_soft/_company_fk` helper（同 2A/2B），建 5 表；新增 `sa.Enum("LESS_THAN","MORE_THAN", name="metercomparator")`，复用 `workorderpriority`；MySQL/SQLite 双方言，无分支。迁移测试在 SQLite 建父表骨架（tb_company/asset/location/user/team）后 upgrade→downgrade 往返。

**接线**：5 个模型注册进 `app/models/__init__.py`（import + `__all__`）；router 挂 `main.py`；Sequence 复用既有 kind 机制（新增 `"meter"`，无需改 sequence_service）。

**测试策略**
- **单元**：`_condition_met`（严格不等、两比较符）；`_decide`（FIRE/REARM/NOOP 全状态）；meter CRUD；trigger CRUD（改 threshold/comparator 重新武装、仅改预设不动武装）；`submit_reading`（发火建单+解武装、回落重武装、一读数多 trigger、disabled/软删 trigger 跳过、复制预设+SOP）；跨租户。
- **API**：meter CRUD；POST reading 返回 `generated_work_order_ids`；trigger CRUD/enable/disable；technician 能提交读数（201）但不能建 meter（403）、不能建 trigger（403）；跨租户 404。
- **契约**：`test_permissions_phase2c.py`。
- **全量回归**：0 failed，alembic 单 head `phase2c_meter`。

## 7. 风险缓解

| 风险 | 缓解 |
|---|---|
| 浮点漂移影响阈值比较 | value/threshold 用 `Numeric(18,4)`；单测覆盖临界小数值（threshold=100.0000，读数 99.9999/100.0001）|
| 发火中途失败致武装态不一致 | `generate_from_trigger` 在同一流程内解武装；`create_work_order` 内部 commit 落地读数+WO；trigger 状态末尾 commit。单条读数通常仅 0–1 发火，风险远低于批处理 |
| `create_work_order` 中途 commit | 与 PM 同模式，已文档化；同步单读数场景风险低 |
| 多 trigger 评估顺序 | 按 `created_at, id` 确定序，结果可复现 |
| 多租户 | 读数提交在请求内（中间件已置租户上下文，**无需 bypass**，区别于 PM 调度器）；router 强校验 `meter.company_id == current_user.company_id` → 404 |
| GPL/Atlas | clean-room，输出无 "Atlas" 字样，不抄源码 |
| 读数 append-only | 本期读数不支持改/删（审计完整性），更正属后期 |

## 完成标准（Definition of Done）

- 全量 pytest 0 failed（含 Meter 单测 + API 测 + 契约/迁移测）。
- `tb_meter` / `tb_meter_reading` / `tb_meter_trigger` / `tb_meter_trigger_assignee` / `tb_meter_trigger_team` 五表经迁移可 upgrade/downgrade。
- `/api/v1/meters` 全套端点工作；提交读数边沿命中自动生单并返回工单 id；technician 能抄表、不能改仪表/触发器；跨租户隔离 404。
- 边沿状态机正确：满足跨入发火并解武装、回落重武装、持续满足不重复发火；编辑 threshold/comparator 重新武装。
- `git status --porcelain` 干净，alembic 单 head `phase2c_meter`。
