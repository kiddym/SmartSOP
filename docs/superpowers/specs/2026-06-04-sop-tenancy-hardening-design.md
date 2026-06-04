# SOP 多租户硬化（NOT NULL + per-company 复合唯一 + Company 层 seed 兜底）设计

> 「SOP 接入认证/多租户 + sop 功能挂闸」（`docs/superpowers/specs/2026-06-04-sop-auth-tenancy-gating-design.md`）的后续轮次。上一轮把 7+2 个 SOP router 接入认证/隔离并挂 `require_feature(Feature.sop)`，但 code-review 暴露两处更深的多租户缺陷：
> - **#3 全局唯一自然键**：`tb_procedure_field.key` 等列是全局 `UNIQUE`（不含 company_id），两个租户用同一自然键会撞唯一约束 → 未捕获 `IntegrityError` 500，且泄露「该键已被别的租户占用」。
> - **#4 NOT-NULL 缺失 + seed 单点**：SOP 表 `company_id` 仍 `NullableTenantMixin`（可空，"enforcement deferred to Phase 1"），任何无 tenant 上下文的 SOP 写入会静默落 NULL 行而非 fail-closed；且「每公司必有系统数据」只挂在 `auth_service.register()` 单一调用点，无 Company 层强制。

## 目标

把 SOP 多租户从「自动隔离 + 应用层上下文」硬化到「schema 层 fail-closed」：

1. 全部全局唯一的 SOP 自然键改为 `(company_id, 自然键)` per-company 复合唯一（消除跨租户撞键 500）。
2. 全部 SOP 租户表 `company_id` 从 nullable 收紧为 NOT NULL（无上下文的 SOP 写入 fail-closed，杜绝 NULL 死行/跨租户泄露）。
3. 把 Company 建立 + roles/user + SOP seed 收敛到单一 `create_company()` 工厂，使「新公司必有系统数据」成为不可绕过的不变量，而非依赖 `register()` 记得调用。

完成后：两个租户可各自创建同名自定义字段；任何漏设上下文的 SOP 写入在 DB 层即被拒；未来新增的建公司路径（管理台/导入）无法产出缺 seed 的残公司。

## 关键现状（已核实，附先例）

### 既有 per-company 复合唯一先例（直接照搬其模式）
- **平台表（TenantMixin, NOT NULL）**：`Role(company_id, code)`、`User(company_id, email)`、`Sequence(company_id, scope)`、`CompanySettings(company_id)` 单例——均 `UniqueConstraint("company_id", <key>)`。
- **SOP 表（已 per-company 化）**：`HeadingStyleRule(company_id, style_name)`、`NumberingProfile(company_id, pattern_key)`——由迁移 `20260531_0013_dict_tenantization.py` 从全局唯一改造而来，**正是本轮范本**：
  ```python
  with op.batch_alter_table(table, recreate="always") as b:  # SQLite 重建 / MySQL 直接 ALTER
      b.drop_constraint(old_global_uq, type_="unique")
      b.create_unique_constraint(new_uq_name, ["company_id", key])
  ```
- **MySQL 生成列 partial-unique 先例**：`tb_procedure` 的 `current_guard`/`draft_guard`/`active_code_version`（`op.execute(... GENERATED ALWAYS AS ... STORED)` + `ADD CONSTRAINT ... UNIQUE`），用 `.with_variant` 兼容 SQLite。本轮不新增生成列，但确认双方言迁移可行。

### 仍全局唯一、需 per-company 化的 4 处（本轮范围，已确认）
| 表 | 列 | 现状 | 目标 |
|---|---|---|---|
| `tb_procedure_field` | `key` | `UniqueConstraint('key')`（全局） | `(company_id, key)` |
| `tb_procedure_source_docx` | `procedure_group_id` | `unique=True`（全局） | `(company_id, procedure_group_id)` |
| `tb_procedure_asset` | `sha256` | `unique=True`（全局内容去重） | `(company_id, sha256)`——**每公司各存一份**，放弃跨租户字节去重 |
| `tb_procedure_asset_reference` | `(asset_id, procedure_id)` | `Index(unique=True)` | `(company_id, asset_id, procedure_id)` |

> **sha256 决策影响**：原全局唯一是「内容寻址去重」——同字节文件跨租户共用一行。改 per-company 后每公司各存一份（更强隔离、放弃去重省存）。`asset_service` 的去重查找 SELECT 本就被 `do_orm_execute` 按 company 过滤，故服务层逻辑天然变成「本公司内去重」，**无需改服务代码**，仅 schema 约束随之 per-company。

### 全部需收 NOT NULL 的 SOP 租户表（NullableTenantMixin → TenantMixin，已确认「全部」）
`tb_folder` / `tb_folder_sequence` / `tb_procedure` / `tb_procedure_node` / `tb_heading_style_rule` / `tb_numbering_profile` / `tb_heading_learning_event` / `tb_batch_import_job` / `tb_batch_import_item` / `tb_procedure_field` / `tb_procedure_settings` / `tb_procedure_source_docx` / `tb_procedure_asset` / `tb_procedure_asset_reference` / `tb_attachment` / `tb_folder_audit_log` / `tb_procedure_audit_log`（17 表）。

`NullableTenantMixin`（`app/models/base.py`）`company_id` 为 `nullable=True` + index + FK `ondelete="CASCADE"`；`TenantMixin` 仅 `nullable=False` 之差。收紧即「换 mixin + 迁移改列 nullability」。

### 自动隔离事件行为（决定 fail-closed 语义）
`app/tenant_isolation.py`：
- `_before_flush`：仅当 `not is_bypassed()` 且 `get_current_company_id() is not None` 时给新 `TenantScoped` 行盖 `company_id`；否则 no-op（行的 `company_id` 保持 None）。
- `_do_orm_execute`：**仅 SELECT** 加 `company_id == X` 过滤；上下文 None / bypass 时 no-op。**bulk UPDATE/DELETE 不被作用域化**。

收 NOT NULL 后，无上下文的 SOP INSERT → `company_id` 保持 None → **NOT NULL 约束在 flush 时报 `IntegrityError`（fail-closed）**，取代原先的静默 NULL 行。

### 存量数据与 Company 建立
- `auth_service.register()` 是**唯一**生产建公司路径（`platform.py` 仅改订阅、`company.py` 仅读改 `/me`）。
- 存量 NULL-company SOP 行：原 spec 决策「假定无真实 prod 数据」——本轮迁移内 `DELETE WHERE company_id IS NULL`（清掉旧全局 seed 死行）。

## 设计决策（本轮已确认）

1. **NOT NULL 范围 = 全部 17 个 SOP 租户表**（NullableTenantMixin → TenantMixin），fail-closed 最彻底。
2. **复合唯一 = 上述 4 处全部**（含 `sha256` 改 per-company，放弃跨租户去重）。
3. **存量 NULL 行直接删除**（假定无 prod 数据，与上一轮一致）。
4. **单迁移、单 head**：新增一个迁移 `down_revision = p6_commercialization_gating`，双方言（SQLite `batch_alter_table(recreate="always")` + MySQL `ALTER`），按 FK 依赖序删 NULL 行 → 改唯一约束 → 收 NOT NULL。
5. **Company 工厂收敛**：抽 `create_company(db, *, name, email, password, admin_name) -> User`（或 `provision_company`），把建 Company + 设上下文 + 播 roles/user + `seed_tenant_sop` 收进一处；`register()` 改为薄封装调用之。强制「建公司即 seed」不变量。

## 组件与改动

### 1. 模型：4 处复合唯一 + 全表换 mixin
- `app/models/field.py`：`key` 去 `unique=True`，加 `__table_args__ = (UniqueConstraint("company_id", "key", name="uq_procedure_field_company_key"),)`；类基从 `NullableTenantMixin` 换 `TenantMixin`。
- `app/models/source_docx.py`：`procedure_group_id` 去 `unique=True`，加 `(company_id, procedure_group_id)` 复合唯一；换 mixin。
- `app/models/asset.py`：`ProcedureAsset.sha256` 去 `unique=True` 加 `(company_id, sha256)`；`ProcedureAssetReference` 的 `(asset_id, procedure_id)` 唯一索引改 `(company_id, asset_id, procedure_id)`；两类换 mixin。
- 其余 13 个 SOP 模型：`NullableTenantMixin` → `TenantMixin`（`company_id` 类型注解 `str | None` → `str`，去掉可空语义）。
- 约束命名沿用既有风格（`uq_<table>_company_<key>`），与迁移名一致。

> 换 mixin 后 `company_id: Mapped[str]`（非 Optional），需核对各模型/schema 是否有依赖 `company_id` 可空的代码（预期无，自动隔离总会盖值）。

### 2. 迁移：`alembic/versions/<ts>_sop_tenancy_hardening.py`
单文件，`down_revision = "p6_commercialization_gating"`，`revision = "sop_tenancy_hardening"`。`upgrade()` 顺序：
1. **删存量 NULL 行**（按 FK 依赖自底向上：reference/asset/node/sequence/audit/item → 主表）：`op.execute("DELETE FROM <t> WHERE company_id IS NULL")`。先删子表避免 FK RESTRICT/CASCADE 干扰。
2. **改 4 处唯一约束**：照 `20260531_0013` 模式，`batch_alter_table(recreate="always")` 内 `drop_constraint(老全局 uq)` + `create_unique_constraint(新复合)`；`procedure_asset_reference` 改唯一索引（drop+create index unique）。
3. **收 17 表 NOT NULL**：`batch_alter_table` 内 `alter_column("company_id", nullable=False, existing_type=sa.String(36))`。SQLite 经 recreate 重建生效；MySQL `MODIFY COLUMN ... NOT NULL`。
`downgrade()` 反向：放回 nullable、复合唯一改回全局（尽力而为；删除的 NULL 行不可逆，文档注明）。

> 双方言验证：测试库 SQLite 跑 `alembic upgrade head` + `downgrade -1` 往返；MySQL 集成手验（与上一轮一致，列为遗留手验项）。FK `ondelete="CASCADE"` 已在 NullableTenantMixin/TenantMixin 一致，改 nullability 不动 FK。

### 3. Company 工厂收敛
- `app/services/auth_service.py`：抽 `create_company(db, payload) -> User`，内含现有 register 的「查重 slug → 建 Company → flush → 设上下文 → 播 roles/user → `seed_tenant_sop` → commit → reset」全流程；`register(db, payload)` 改为 `return create_company(db, payload)`（或直接重命名 + 保留 register 薄封装以不破坏 router 调用）。
- 目的：未来任何建公司路径（管理台/导入脚本）只准走 `create_company`，seed 与上下文设定不可遗漏。在 `create_company` docstring + 可选 `assert` 注明「禁止裸 `db.add(Company(...))`」。
- 不在本轮新增管理台建公司端点（无需求），仅把唯一路径工厂化以承接未来。

### 4. fail-closed 语义（NOT NULL 兜底 + 可选显式报错）
- NOT NULL 收紧后，无上下文 SOP INSERT 在 flush 报 `IntegrityError`（500），已是 fail-closed。
- **可选增强**：`_before_flush` 增加——当存在新 `TenantScoped` 行、未 bypass、但 `get_current_company_id() is None` 时，`raise` 一个清晰错误（如 `TenantContextMissing`），把 500 IntegrityError 升级为可诊断的显式异常。**列为本轮可选**（默认采用，因诊断价值高且改动小），若引入测试 churn 过大则降级为后续。

### 5. Attachment / audit-log 特殊核查（最大风险）
- `tb_attachment` 是**多态单表**（procedure / asset / work_order / part…），其租户性派生自宿主；据通用附件设计，procedure 宿主解析走 `bypass_tenant_scope()`。**bypass 下 `_before_flush` 不盖 `company_id`** → 收 NOT NULL 后这些写路径会 500。
- 因此本轮对 attachment：必须让**附件创建时显式从宿主实体取 `company_id` 落库**（而非依赖自动盖值），再收 NOT NULL；否则 attachment 写路径 fail-closed 误伤。这是独立子任务，须先审计所有 attachment 写入点。
- 两张 audit-log 表在 SOP 操作中写入（彼时 `require_feature` 已设上下文），预期自动盖值生效；仍须逐写入点核实无 bypass/无上下文路径。

## 数据流（硬化后）

```
建公司：create_company()  ← 唯一入口
  设上下文 → 播 roles/user + SOP seed（before_flush 盖 company_id）→ commit
SOP 写入（经 require_feature 设上下文）
  before_flush 盖 company_id=co → NOT NULL 满足 → 写入
SOP 写入（漏设上下文 / bypass 且未显式盖值）
  company_id=None → NOT NULL 约束拒绝 → IntegrityError（fail-closed）
  （可选）before_flush 提前 raise TenantContextMissing（可诊断）
两租户同自然键（如 field.key="risk_grade"）
  各自 (company_id,key) 不冲突 → 均成功（#3 修复）
```

## 边界与非目标

- 不新增管理台「建公司」端点（仅工厂化唯一现有路径）。
- 不处理 bulk UPDATE/DELETE 不被 `do_orm_execute` 作用域化的问题（独立风险，本轮仅在测试迁移核查中留意；如发现 SOP 服务用未作用域化的 bulk 写，记后续）。
- 不改自动隔离事件的 SELECT 过滤机制本身（除可选的 before_flush fail-closed 报错）。
- 不回填存量 NULL 行（按决策删除）。

## 风险

1. **Attachment bypass × NOT NULL**（最高）：附件写路径在 bypass 下不会自动盖 company_id，收 NOT NULL 前必须改为显式从宿主落值，否则 500 误伤所有附件上传。须先审计写入点。
2. **17 表迁移面大**：每表 NULL 行删除 + nullability 改；SQLite 经 `batch_alter_table(recreate="always")` 重建，须确认重建保留所有列/索引/FK/生成列（`tb_procedure` 有生成列 `current_guard` 等——recreate 须正确携带，参照 0013 是否触及生成列表）。
3. **换 mixin 的类型收紧**：`company_id: Mapped[str]` 可能触发 mypy 对既有 `company_id is None` 判断的告警；逐一核实。
4. **复合唯一改造的既有数据**：测试/夹具中直接 `db.add` 造的 SOP 行若曾依赖全局唯一去重，改 per-company 后行为变化（预期仅放宽，不收紧）。
5. **MySQL 集成未自动验证**：单测 SQLite；生成列 partial-unique 与 NOT NULL 在 MySQL 的行为须手验。

## 验收标准

- 4 处自然键为 `(company_id, …)` 复合唯一；两租户同 key 创建均成功（#3 回归红→绿）。
- 17 个 SOP 表 `company_id` NOT NULL；无上下文 SOP 写入 fail-closed（IntegrityError 或显式 TenantContextMissing），不再产生 NULL 行。
- `create_company()` 为唯一建公司工厂，必播 SOP seed；`register()` 经其实现；绕过工厂裸建 Company 在测试中被证伪/告警。
- Attachment 写路径显式落宿主 company_id，收 NOT NULL 后附件上传/下载/预览/删全绿。
- 后端 `pytest` 全量绿、ruff/format/mypy 净；`alembic heads` 单 head（新迁移）；`alembic upgrade head` + `downgrade -1` 在 SQLite 往返通过。
- 前端无新增改动（schema 硬化，API 契约不变）。
