# SOP 接入认证/多租户 + sop 功能挂闸 设计

> P6 商业化门控（`docs/superpowers/specs/2026-06-04-p6-commercialization-gating-design.md`）的后续轮次。P6 本体已合并（PR #2），其中 `Feature.sop` 已进入 catalog 但**整体推迟挂闸**：`procedures / procedure_groups / nodes / parse / heading_rules / folders` 这 6 个 SOP router 是认证/多租户整合之前的全局无鉴权端点，挂 `require_feature`（依赖登录）会让 ~80 个无 token 的 integration 测试变 401。本轮补做这道整合。

## 目标

给 7 个 SOP router（上述 6 个 + `batch_imports`）接入认证与多租户隔离，并挂上 `require_feature(Feature.sop)` 闸门；同时让前端侧边栏对 SOP 模块显示锁标。完成后：free 档访问 SOP → 402；pro/enterprise 档可访问且数据按公司隔离。

## 关键现状（已核实）

- **租户隔离已全自动**：`backend/app/tenant_isolation.py` 在全局 `Session` 上注册了两个事件——
  - `_before_flush`：按 tenant 上下文给新建的 `TenantScoped` 行自动盖 `company_id`；
  - `_do_orm_execute`：对所有 `TenantScoped` 子类（含 SOP 表）自动按 `company_id` 过滤 SELECT。
  - 两事件在 `tenant.get_current_company_id() is None` 或 `is_bypassed()` 时 no-op。
- **SOP 模型已租户化但 nullable**：`folder / procedure / node / heading_rule / heading_learning_event / batch / sequence / settings / field` 均继承 `NullableTenantMixin`（`backend/app/models/base.py`，company_id 可空，"enforcement deferred to Phase 1"）。
- **SOP router 现状**：`procedures / procedure_groups / nodes / parse / heading_rules / folders` 不 import `get_current_user`，底层 service 不接 company_id；正因请求没设 tenant 上下文，自动隔离事件 no-op，故表现为"单租户/全局"。`batch_imports` 已有 per-endpoint `get_current_user`。
- **`require_feature` 的副作用链**：`require_feature(f)` → `Depends(get_current_user)` → `get_current_user` 调 `tenant.set_current_company_id(company_id)`。即**单个 `require_feature(Feature.sop)` 依赖同时完成认证 + 设租户上下文 + 功能闸门**。
- **register() 已有每公司播种模式**：`backend/app/services/auth_service.py` 的 `register()` 先 `tenant.set_current_company_id(new_company.id)`，再播种 roles/user。
- **启动全局 seed**：`backend/app/main.py` lifespan 调 `run_seed(db)`（`backend/app/seed.py`），建系统文件夹「废止/归档」、默认 `ProcedureSettings`、示例 `ProcedureField`——均为 NULL company_id 的全局行；`run_seed` 内容**全部是 SOP 相关**。

## 设计决策（已与人确认）

1. **系统/seed 数据：每公司各播一份**。不放宽过滤；过滤保持严格 `company_id == X`。
2. **存量数据：假定无真实 prod 数据**，视为新启用。不为存量 NULL 行做归属回填。
3. **认证粒度：仅 `get_current_user`**（经 `require_feature` 内含），不为 SOP 新增 RBAC 权限码（留后续）。
4. **company_id 保持 `NullableTenantMixin`**：require_feature 依赖保证所有 SOP 路由都有 tenant 上下文，新行必被自动盖值；NOT-NULL 硬化留作后续。
5. **本轮无新 alembic 迁移**：无 schema 变更、无回填。单 head 维持 `p6_commercialization_gating`。

## 组件与改动

### 1. SOP router 挂依赖

给 6 个无鉴权 router 各加 router 级 `dependencies=[Depends(require_feature(Feature.sop))]`：
`procedures.py` / `procedure_groups.py` / `nodes.py` / `parse.py` / `heading_rules.py` / `folders.py`。
`batch_imports.py` 已有 per-endpoint `get_current_user`，补 router 级 `require_feature(Feature.sop)`。

该依赖三合一：① 强制登录（free 公司也需登录态）；② 设 tenant 上下文 → 自动隔离接管查询/插入；③ sop 闸门（free→402，pro/enterprise→放行）。

> 顺序保证：FastAPI 先解析依赖再进 handler，故 handler 内 db 查询发生时 tenant 上下文已就绪。

### 2. 每公司播种 SOP 系统数据

重构 `backend/app/seed.py`：抽出一个按"当前 tenant 上下文"创建 SOP 系统数据的函数（系统文件夹「废止/归档」、默认 `ProcedureSettings`、示例 `ProcedureField`），其幂等检查改为 tenant-scoped（依赖自动过滤即按本公司判重）。

在 `auth_service.register()` 播完 roles/user 后调用该函数（上下文已是新公司，`_before_flush` 自动盖 company_id）。

**移除 `main.py` lifespan 中的 `run_seed(db)` 调用**：每公司播种后，启动时全局播种只会建出 NULL-company 的不可见死行，且可能与每公司播种撞唯一约束。决定：**保留 `run_seed` 函数本身**（不删，避免牵连其引用/测试），仅删去 lifespan 里的调用；新的每公司播种函数与 `run_seed` 共享底层 seed 逻辑以免重复。

> 需核实：folder 等是否有"全局唯一"约束会被每公司播种违反（预期唯一性是 per-company，因 company_id 进入约束）；实现时确认。

### 3. 前端补 sop 锁标

`frontend/src/components/AppSidebar.vue`：给 SOP 组的「程序库 / 草稿箱 / 文件夹」三项加 `feature: 'sop'`（「审计日志」是 `audit_logs` router，非 SOP，不加）。Task 11 已有 `isLocked`/`menuIndex` 锁标机制，直接复用。

### 4. 测试改造（本轮主要工作量与风险）

约 9 个 integration 文件现在无 token 调 SOP 端点（`test_procedures / test_folders / test_nodes_api / test_batch_imports_api / test_batch_apply_api / test_editor / test_pdf / test_version_management / test_word_import / test_attachments` 等），接认证 + 挂闸后会 401/402。

方案：在 conftest 提供一个共享 fixture，**经各 SOP 测试文件 `pytestmark = pytest.mark.usefixtures(...)` 整文件引用**（不放 `tests/integration/conftest.py` 做 autouse，以免干扰同目录下已自带认证的非 SOP 测试如 audit_logs）。该 fixture：
- 经 `_enterprise_default`（已存在的 before_insert fixture，把新公司升 enterprise 以解锁 sop）注册一家公司；
- 用 httpx `TestClient` 默认 header（`client.headers["Authorization"] = ...`）让后续所有 `client.xxx()` 自动带 token，**测试体几乎不动**。

少量断言需逐个微调：每公司现在自带 2 个系统文件夹 + 默认设置，依赖"初始空状态"的计数/树断言会变。

> 非 SOP 的 integration 测试（attachments 的 attachment 端点、audit_logs 等）已自带认证，autouse 预认证对它们无害（默认 header 不影响其显式注册的其他公司）；但需确认没有"显式测 401 无 token"的 SOP 用例被默认 header 干扰——如有，该用例临时清除默认 header。

### 5. 单测调整

- `backend/tests/test_feature_gating.py`：把 SOP 代表端点从"推迟说明"移回 `_LOCKED_ENDPOINTS`（如 `/api/v1/procedures`、`/api/v1/folders`），验证 free→402；并加 pro 档可访问用例。
- 新增 `backend/tests/test_sop_tenant_seed.py`（或并入既有）：
  - 注册即每公司自带系统文件夹（「废止/归档」可见且属本公司）；
  - 跨租户隔离：公司 A 建的文件夹/程序，公司 B 查询不可见（404/不在列表）。

## 数据流

```
登录用户请求 SOP 端点
  → require_feature(Feature.sop) 依赖：
      get_current_user 解码 token → tenant.set_current_company_id(co)
      effective_features(plan,status) 含 sop？ 否→402 / 是→放行
  → handler 内 db 查询/写入
      _do_orm_execute 自动加 company_id==co 过滤
      _before_flush 自动给新行盖 company_id=co
注册新公司
  → register() 设上下文=新公司 → 播种 roles/user + SOP 系统数据（自动盖 company_id）
```

## 边界与非目标

- 不新增 SOP RBAC 权限码（任何本公司登录用户可操作 SOP，与现状一致）。
- 不收紧 company_id 为 NOT NULL（保持 NullableTenantMixin）。
- 不为存量 NULL 行做归属回填（假定无 prod 数据）。
- 不改自动隔离机制本身。

## 风险

1. **测试改造 churn**：~9 文件 + 计数断言微调，是最大工作量与回归风险源。逐文件迁移、立即跑绿，不堆积。
2. **每公司播种 × 测试断言**：初始多了系统文件夹/设置，影响计数/树/首个 code 断言。
3. **移除启动 seed**：确认无其他路径依赖全局 seed 行（已知 run_seed 全为 SOP）。
4. **唯一约束**：每公司播种系统文件夹需确认唯一约束含 company_id，否则第二家公司播种会冲突。
5. **dev 环境**：`running-smartsop-dev` 启动后空库注册首公司才有 SOP 系统数据；手动验证一条龙（注册→访问 SOP→跨公司隔离）。

## 验收标准

- 7 个 SOP router 挂 `require_feature(Feature.sop)`；free→402、pro/enterprise→可访问且按公司隔离。
- 注册新公司自动获得本公司 SOP 系统数据；跨租户不可见彼此 SOP 数据。
- 前端侧边栏 SOP 三项在 free 档显示锁标并引导套餐页。
- 后端 `pytest` 全量绿、ruff/format/mypy 净、alembic 单 head。
- 前端 vitest 全量绿、vue-tsc/eslint 净。
