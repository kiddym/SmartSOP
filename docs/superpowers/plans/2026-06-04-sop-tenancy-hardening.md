# SOP 多租户硬化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按 task 逐个 TDD 执行。步骤用 checkbox（`- [x]`）跟踪。

**Goal:** 把 SOP 多租户从应用层硬化到 schema 层——4 处全局唯一自然键改 `(company_id, …)` 复合唯一；17 个 SOP 租户表 `company_id` 收 NOT NULL（fail-closed）；Company 建立 + seed 收敛到单一 `create_company()` 工厂；附件写路径显式落宿主 company_id。

**Architecture:** 测试库走 `Base.metadata.create_all`（非 alembic），故**模型 `__table_args__`/mixin 改动即驱动测试行为**；alembic 迁移是并行交付物，用 `upgrade head`+`downgrade -1` 在 SQLite 往返单独验证，MySQL 手验。NOT NULL 收紧后，无 tenant 上下文的 SOP 写入由 DB 约束 fail-closed。

**Tech Stack:** FastAPI + SQLAlchemy（自动隔离事件）+ Alembic（双方言 SQLite/MySQL）+ pytest。

设计依据：`docs/superpowers/specs/2026-06-04-sop-tenancy-hardening-design.md`。

---

## 契约（全程以此为准）

- **4 处复合唯一**：`procedure_field(company_id,key)` / `procedure_source_docx(company_id,procedure_group_id)` / `procedure_asset(company_id,sha256)` / `procedure_asset_reference(company_id,asset_id,procedure_id)`。两租户同自然键均成功。
- **17 表 NOT NULL**：全部 NullableTenantMixin SOP 表 → TenantMixin。无上下文 SOP 写入 fail-closed（IntegrityError / 显式 TenantContextMissing），不再落 NULL 行。
- **单一建公司工厂** `create_company()`：必播 SOP seed；`register()` 经其实现。
- **附件**：写入显式从宿主取 company_id（bypass 下自动盖值不生效）。
- **单 head**：新增迁移 `down_revision = p6_commercialization_gating`；`alembic upgrade head`+`downgrade -1` 在 SQLite 往返通过。
- **前端无改动**（schema 硬化，API 契约不变）。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `backend/app/models/field.py` | 修改 | key 去全局 unique→`(company_id,key)`；换 TenantMixin |
| `backend/app/models/source_docx.py` | 修改 | procedure_group_id 复合唯一；换 TenantMixin |
| `backend/app/models/asset.py` | 修改 | sha256/(asset_id,procedure_id) 复合唯一；两类换 TenantMixin |
| `backend/app/models/{folder,procedure,node,heading_rule,numbering_profile,heading_learning_event,batch,settings,attachment,audit}.py` | 修改 | NullableTenantMixin→TenantMixin（13 余表） |
| `backend/app/services/auth_service.py` | 修改 | 抽 `create_company()`；register 薄封装 |
| `backend/app/services/<attachment 写入服务>.py` | 修改 | 创建附件时显式落宿主 company_id |
| `backend/app/tenant_isolation.py` | 修改（可选） | before_flush 对无上下文新 TenantScoped 行 raise TenantContextMissing |
| `backend/alembic/versions/<ts>_sop_tenancy_hardening.py` | 创建 | 删 NULL 行→4 复合唯一→17 表 NOT NULL；down 反向 |
| `backend/tests/test_sop_tenancy_hardening.py` | 创建 | 复合唯一两租户 + NOT NULL fail-closed + create_company 不变量 |
| `backend/tests/test_migration_roundtrip.py`（或并入既有迁移测试） | 创建/修改 | alembic upgrade/downgrade 往返 |
| `backend/tests/**`（SOP 行无上下文造数据者） | 修改 | 补 tenant 上下文（NOT NULL 后必需） |

---

## Task 1: 附件写路径显式落宿主 company_id（NOT NULL 前置，最高风险）

> 附件多态表在 bypass 下解析宿主，`_before_flush` 不盖 company_id；收 NOT NULL 前必须改为显式落值，否则附件上传全 500。先做此项解风险。

**Files:**
- Modify: 附件创建服务（执行时 `grep -rn "Attachment(" app/services app/routers` 定位写入点）
- Test: `backend/tests/integration/test_attachments.py`（已在上一轮接 `_sop_auth`）

- [x] **Step 1: 审计写入点** —— `grep -rn "Attachment(" app/` 列出所有构造 Attachment 的位置；确认哪些在 `bypass_tenant_scope()` 下执行（尤其 procedure 宿主路径，见通用附件设计）。读 `app/models/attachment.py` 确认 `company_id` 现为 NullableTenantMixin。

- [x] **Step 2: 写失败测试** —— 在 `test_attachments.py` 加：在 `_sop_auth` 公司下经 API 建 procedure + 上传附件后，直接查库断言 `attachment.company_id == _sop_auth 的 company_id`（当前若走 bypass 落 NULL → FAIL）。`.venv/bin/python -m pytest tests/integration/test_attachments.py -q -p no:cacheprovider` 跑红该用例。

- [x] **Step 3: 实现** —— 附件创建处显式从宿主实体取 `company_id` 赋给新 `Attachment`（宿主已是某公司的 procedure/asset/...）。执行时按 entity_registry 解析宿主后取其 `company_id`。保持附件「非租户边界、宿主才是」语义不变——附件归属随宿主。

- [x] **Step 4: 跑绿** 该文件全绿。门禁：`.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app`。

- [x] **Step 5: Commit** `git commit -m "fix(sop): 附件创建显式落宿主 company_id（为 NOT NULL 硬化铺路）"`

---

## Task 2: 4 处全局唯一 → per-company 复合唯一（#3 核心）

> 测试走 create_all，模型改 `__table_args__` 即生效。先在模型层做完，迁移留 Task 5 统一写。

**Files:**
- Modify: `backend/app/models/field.py` / `source_docx.py` / `asset.py`
- Test: `backend/tests/test_sop_tenancy_hardening.py`

- [x] **Step 1: 写失败测试** —— 新建 `test_sop_tenancy_hardening.py`：两个公司各设上下文，各建一条 `ProcedureField(key="risk_grade")`，断言**均成功且 company_id 各异**（当前全局 unique → 第二条撞 `IntegrityError` → FAIL）。同理对 `ProcedureAsset.sha256`（同 sha256 两公司各一行）。用 `tenant.set_current_company_id` 切上下文 + 两个 Company。`-p no:cacheprovider` 跑红。

> 执行时先 `grep -n "unique=True\|UniqueConstraint" app/models/field.py app/models/source_docx.py app/models/asset.py` 核实现状约束名，迁移 drop 时要用真实旧名（`uq_tb_procedure_field_key` 等）。

- [x] **Step 2: 改模型复合唯一** ——
  - `field.py`：`key` 去 `unique=True`；加 `__table_args__ = (UniqueConstraint("company_id", "key", name="uq_procedure_field_company_key"),)`。
  - `source_docx.py`：`procedure_group_id` 去 `unique=True`；加 `(company_id, procedure_group_id)` 复合唯一。
  - `asset.py`：`ProcedureAsset.sha256` 去 `unique=True` 加 `(company_id, sha256)`；`ProcedureAssetReference` 的唯一索引 `(asset_id, procedure_id)` → `(company_id, asset_id, procedure_id)`。
  （命名沿用 `uq_<table>_company_<key>`，与 Task 5 迁移一致。）

- [x] **Step 3: 跑绿** 新测试 PASS。回归 `tests/integration/test_fields.py`（含 `test_create_duplicate_key_409`——本公司内同 key 仍须 409，确认复合唯一不破坏同租户查重）+ asset/source_docx 相关测试。

- [x] **Step 4: 门禁 + Commit** `git commit -m "feat(sop): procedure_field.key 等 4 处自然键改 (company_id, …) 复合唯一"`

---

## Task 3: Company 建立工厂 `create_company`（#4 seed 不变量）

**Files:**
- Modify: `backend/app/services/auth_service.py`
- Test: `backend/tests/test_sop_tenancy_hardening.py`（追加）/ `tests/test_auth_service.py`

- [x] **Step 1: 写失败/约束测试** —— 断言「经 `create_company` 建的公司必有系统文件夹 + 设置」（已有 `test_sop_tenant_seed.py` 覆盖部分，可复用）；并加测试证明 `create_company` 是建公司+seed 的单一入口（调用 `create_company` 后该公司 `seed` 齐全）。若 `create_company` 尚不存在 → import 报错 FAIL。

- [x] **Step 2: 抽工厂** —— 把 `register()` 的全流程（slug 查重→建 Company→flush→设上下文→播 roles/user→`seed_tenant_sop`→commit→reset）抽成 `create_company(db, payload) -> User`；`register()` 改为 `return create_company(db, payload)`。docstring 注明「唯一建公司入口，禁止裸 `db.add(Company(...))`」。

- [x] **Step 3: 跑绿** `tests/test_auth_api.py tests/test_auth_service.py tests/test_sop_tenant_seed.py` 全绿。

- [x] **Step 4: 门禁 + Commit** `git commit -m "refactor(sop): 抽 create_company 工厂，强制建公司即播 SOP seed"`

---

## Task 4: 17 表 company_id → NOT NULL（fail-closed）+ 测试上下文补齐（本轮主要工作量）

> 模型换 mixin 即让 create_all 建 NOT NULL 列。随后所有「无 tenant 上下文造 SOP 行」的测试会 IntegrityError——逐文件补上下文，立即跑绿，不堆积。

**Files:**
- Modify: 17 个 SOP 模型（NullableTenantMixin→TenantMixin）
- Modify（可选）: `backend/app/tenant_isolation.py`
- Modify: 受影响测试（含 `tests/unit/test_seed.py`、各无上下文造 SOP 行的单测）
- Test: `backend/tests/test_sop_tenancy_hardening.py`（追加 fail-closed）

- [x] **Step 1: 写失败测试** —— 追加：在**无 tenant 上下文**（`_clear_tenant_context` 默认 None）下 `db.add(Folder(...)); db.flush()` 断言抛 `IntegrityError`（或可选的 `TenantContextMissing`）。当前 nullable → 不抛 → FAIL。

- [x] **Step 2: 换 mixin** —— 17 个 SOP 模型基类 `NullableTenantMixin` → `TenantMixin`；`company_id` 注解随 TenantMixin 变 `Mapped[str]`。执行时逐文件 `grep -n "NullableTenantMixin"` 改 import + 基类。

- [x] **Step 3:（可选）before_flush 显式报错** —— `tenant_isolation.py` `_before_flush`：遍历 `session.new` 若有 `TenantScoped` 且非 bypass 且 `get_current_company_id() is None` → `raise TenantContextMissing(...)`。默认采用（诊断价值高）；若引入过大 churn 则回退为仅靠 NOT NULL IntegrityError。

- [x] **Step 4: 跑红全量，逐文件补上下文** —— `.venv/bin/python -m pytest -q -p no:cacheprovider` 找出因 NOT NULL 而 IntegrityError 的测试。逐个修：
  - 走 `_sop_auth` 的 integration 测试：上下文已设，通常无碍。
  - 无上下文的单测/service 测试（直接 `db.add` SOP 行）：用 `tenant.set_current_company_id(cid)` 包裹，或引入轻量 fixture 设上下文 + 建 Company。
  - `tests/unit/test_seed.py`：`run_seed` 无上下文会落 NULL → 现 NOT NULL 报错。改为在测试内设上下文，或让 `run_seed` 要求上下文（更新其 docstring「不再支持无上下文全局行」）。
  每改一文件即跑绿，不堆积。

> 执行原则：只补 tenant 上下文，不改业务断言语义。`mypy` 会因 `company_id` 不再 Optional 报既有 `is None` 判断——逐一核实并调整。

- [x] **Step 5: 门禁** `.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app` 净。

- [x] **Step 6: Commit** `git commit -m "feat(sop): 17 个 SOP 租户表 company_id 收 NOT NULL（fail-closed）+ 测试补上下文"`

---

## Task 5: Alembic 迁移（删 NULL→复合唯一→NOT NULL）+ 往返验证

> 模型已是最终态；本任务让真实 DB（MySQL/dev）追上。参照 `20260531_0013_dict_tenantization.py` 的双方言 `batch_alter_table(recreate="always")` 模式。

**Files:**
- Create: `backend/alembic/versions/<ts>_sop_tenancy_hardening.py`
- Test: `backend/tests/test_migration_roundtrip.py`（或既有迁移测试）

- [x] **Step 1: 生成迁移骨架** —— `revision = "sop_tenancy_hardening"`，`down_revision = "p6_commercialization_gating"`。`.venv/bin/alembic heads` 确认基线单 head。

- [x] **Step 2: 写 upgrade()** 顺序：
  1. **删 NULL 行**（按 FK 依赖自底向上：reference→asset、node/sequence/audit/item→主表）`op.execute("DELETE FROM <t> WHERE company_id IS NULL")`。执行时 `grep` 各表 FK 关系定序。
  2. **4 处复合唯一**：`batch_alter_table(recreate="always")` 内 `drop_constraint(旧全局 uq, type_="unique")` + `create_unique_constraint(新复合)`；asset_reference 改唯一索引（drop+create unique index）。旧约束名用 Step（Task2）核实的真名。
  3. **17 表 NOT NULL**：`batch_alter_table` 内 `alter_column("company_id", existing_type=sa.String(36), nullable=False)`。
- [x] **Step 3: 写 downgrade()** 反向（nullable 还原、复合唯一改回全局；注明删除的 NULL 行不可逆）。

> 风险核实：`tb_procedure` 含生成列 `current_guard/draft_guard/active_code_version`，`batch_alter_table(recreate="always")` 重建须正确携带生成列与其 UNIQUE——执行时参照 0013/initial 迁移确认 recreate 不丢生成列；必要时该表单独用 MySQL `MODIFY COLUMN` 而非 batch recreate（`.with_variant` 分方言）。

- [x] **Step 4: 往返测试** —— `test_migration_roundtrip.py`：从 `p6_commercialization_gating` 起 `alembic upgrade head` 在全新 SQLite 库通过；`downgrade -1` 不报错。`.venv/bin/alembic heads` 仍单 head（=`sop_tenancy_hardening`）。

- [x] **Step 5: 门禁 + Commit** `git commit -m "feat(sop): alembic 迁移 sop_tenancy_hardening（删 NULL+复合唯一+NOT NULL）"`

---

## Task 6: 全量收尾 + 手验

- [x] **Step 1: 后端全量** `.venv/bin/python -m pytest -q -p no:cacheprovider` 全绿。
- [x] **Step 2: 门禁** ruff/format/mypy 净；`alembic heads` 单 head。
- [x] **Step 3: 前端回归** `cd frontend && npx vitest run`（预期无改动仍全绿，确认 schema 硬化未触前端契约）。
- [x] **Step 4: dev 手验**（`running-smartsop-dev`）：注册 enterprise 公司 A、B，各建同 key 自定义字段（均成功，#3 修复）；确认 A 看不到 B 的字段；构造一次无上下文 SOP 写（脚本）确认 fail-closed。记录结论。**MySQL 集成迁移手验**：在 MySQL dev 库 `alembic upgrade head`，验证 NOT NULL + 复合唯一 + 生成列保留。
- [x] **Step 5: Commit（如有）** `git commit -m "chore(sop): 多租户硬化收尾" || echo 无改动`

---

## Self-Review（执行后记录结论）

**Spec 覆盖核对**：
- §组件1 复合唯一 → Task 2 ✓
- §组件2 迁移 → Task 5 ✓
- §组件3 create_company → Task 3 ✓
- §组件4 fail-closed（NOT NULL + 可选报错）→ Task 4 ✓
- §组件5 附件特殊核查 → Task 1 ✓
- §验收标准各项 → 分散 Task 2/3/4/5/6 ✓

**已知执行注意**：
1. Task 1（附件 bypass×NOT NULL）是 NOT NULL 的前置解锁项，须最先做。
2. Task 4 测试补上下文是主要 churn（同上一轮 ~77 测试规模，且波及无上下文的单测/service 测试与 `run_seed`/`test_seed`）；逐文件跑绿，不堆积。
3. Task 5 `tb_procedure` 生成列在 SQLite `recreate="always"` 下不可丢；必要时分方言处理。
4. MySQL 集成（NOT NULL/复合唯一/生成列 partial-unique）仅手验，列为遗留。
5. `mypy` 因 `company_id` 去 Optional 会暴露既有 `is None` 判断，逐一核实。
