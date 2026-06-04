# SOP 接入认证/多租户 + sop 功能挂闸 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 7 个 SOP router 接入认证与多租户隔离并挂 `require_feature(Feature.sop)` 闸门，注册时每公司各播一份 SOP 系统数据，前端侧边栏对 SOP 显示锁标。

**Architecture:** 复用既有自动机制——`require_feature(Feature.sop)` 这一个 router 级依赖三合一（强制登录 + 经 get_current_user 设 tenant 上下文触发 `app/tenant_isolation.py` 自动隔离 + sop 闸门）；每公司播种复用现有 seed 函数（在 tenant 上下文下天然 per-company 幂等），接入 `register()`；移除启动全局 seed。本轮无 schema 变更、无新迁移。

**Tech Stack:** FastAPI + SQLAlchemy（自动隔离用 Session 事件 `before_flush`/`do_orm_execute`）+ pytest（后端）；Vue 3 + Pinia + Element Plus + Vitest（前端）。

设计依据：`docs/superpowers/specs/2026-06-04-sop-auth-tenancy-gating-design.md`。

---

## 契约（全程以此为准）

- **挂闸 router（7 个）**：`procedures` / `procedure_groups` / `nodes` / `parse` / `heading_rules` / `folders` / `batch_imports`，全部用 router 级 `dependencies=[Depends(require_feature(Feature.sop))]`。
- **HTTP 语义**：SOP 端点在 free 档 → 402（`detail.code == "FEATURE_LOCKED"`）；pro/enterprise 档 → 正常（且按 company 隔离）。
- **每公司 SOP 系统数据**：注册即自动获得本公司的「废止」「归档」系统文件夹 + 默认 `ProcedureSettings` + 示例 `ProcedureField`，均按 company_id 隔离。
- **无新 alembic 迁移**，单 head 维持 `p6_commercialization_gating`。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `backend/app/seed.py` | 修改 | 抽出 `seed_tenant_sop(db)`（三个 seed 不 commit）；`run_seed` 复用之 |
| `backend/app/services/auth_service.py` | 修改 | `register()` 播完 roles/user 后调 `seed_tenant_sop(db)` |
| `backend/app/main.py` | 修改 | 移除 lifespan 中 `run_seed(db)` 调用 + 清理 import |
| `backend/app/routers/{folders,procedures,procedure_groups,nodes,parse,heading_rules,batch_imports}.py` | 修改 | router 加 `dependencies=[Depends(require_feature(Feature.sop))]` + import |
| `backend/tests/conftest.py` | 修改 | 加共享 fixture `_sop_auth`（注册+enterprise+默认 token+设 tenant 上下文） |
| `backend/tests/test_sop_tenant_seed.py` | 创建 | 每公司播种 + 跨租户隔离单测 |
| `backend/tests/test_feature_gating.py` | 修改 | 把 SOP 端点移回 locked 列表 |
| `backend/tests/integration/test_*.py`（10 个 SOP 文件） | 修改 | `pytestmark` 引用 `_sop_auth` + 断言微调 |
| `frontend/src/components/AppSidebar.vue` | 修改 | SOP 三项加 `feature: 'sop'` |
| `frontend/tests/unit/AppSidebar.spec.ts` | 修改（如需） | 适配锁标 |

---

## Task 1: 每公司 SOP 播种 + 接入 register + 移除启动 seed

**Files:**
- Modify: `backend/app/seed.py`
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_sop_tenant_seed.py`

> 说明：本任务不依赖 SOP router 是否挂闸——直接在 service/db 层验证「注册→每公司有自家系统文件夹」与「跨租户不可见」，借自动隔离事件（已存在）。

- [ ] **Step 1: 写失败测试** `backend/tests/test_sop_tenant_seed.py`

```python
"""每公司 SOP 播种 + 跨租户隔离（借自动隔离事件，不经 SOP router）。"""

from __future__ import annotations

from sqlalchemy import select

from app import tenant
from app.models.folder import Folder
from app.schemas.auth import RegisterRequest
from app.services import auth_service

DEPRECATED = "废止"
ARCHIVED = "归档"


def _register(db, *, name, email):
    return auth_service.register(
        db, RegisterRequest(company_name=name, email=email, password="secret123", name="Admin")
    )


def _system_folder_names(db, company_id):
    token = tenant.set_current_company_id(company_id)
    try:
        rows = db.execute(select(Folder).where(Folder.system.is_(True))).scalars().all()
        return {f.name for f in rows}
    finally:
        tenant.reset_current_company_id(token)


def test_register_seeds_system_folders_per_company(db):
    user = _register(db, name="Acme", email="a@acme.com")
    names = _system_folder_names(db, user.company_id)
    assert {DEPRECATED, ARCHIVED} <= names


def test_seed_folders_are_tenant_isolated(db):
    a = _register(db, name="Acme", email="a@acme.com")
    b = _register(db, name="Beta", email="b@beta.com")
    # 各自只看到自家系统文件夹，看不到对方的（数量上互不叠加）
    a_rows = _system_folders(db, a.company_id)
    b_rows = _system_folders(db, b.company_id)
    assert all(f.company_id == a.company_id for f in a_rows)
    assert all(f.company_id == b.company_id for f in b_rows)
    assert {f.id for f in a_rows}.isdisjoint({f.id for f in b_rows})


def _system_folders(db, company_id):
    token = tenant.set_current_company_id(company_id)
    try:
        return db.execute(select(Folder).where(Folder.system.is_(True))).scalars().all()
    finally:
        tenant.reset_current_company_id(token)
```

> 执行时先 `grep -n "class RegisterRequest" app/schemas/auth.py` 核实字段名（company_name/email/password/name），与 `register()` 签名对齐；不符则按真实字段微调。

- [ ] **Step 2: 跑红** `cd backend && .venv/bin/python -m pytest tests/test_sop_tenant_seed.py -v` → FAIL（register 尚未播种 SOP → 系统文件夹不存在或非本公司）。

- [ ] **Step 3: seed.py 抽出 `seed_tenant_sop`** —— `backend/app/seed.py`，把 `run_seed` 改为复用新函数：

```python
def seed_tenant_sop(db: Session) -> None:
    """为当前 tenant 上下文播种 SOP 系统数据（不 commit）。

    三个 seed 内部用 select/add，在 tenant 上下文下由 app/tenant_isolation.py 事件
    自动按 company_id 过滤判重并盖值，故天然每公司幂等。供 register() 在已设上下文时调用。
    """
    seed_system_folders(db)
    seed_settings(db)
    seed_sample_field(db)


def run_seed(db: Session) -> None:
    """执行全部种子（幂等）。无 tenant 上下文时建全局行（仅供脚本/历史用途）。"""
    seed_tenant_sop(db)
    db.commit()
```

- [ ] **Step 4: register 接入播种** —— `backend/app/services/auth_service.py`：import 区加 `from app.seed import seed_tenant_sop`；在 `register()` 的 `db.add(user)` 之后、`db.commit()` 之前插入：

```python
        db.add(user)
        db.flush()
        seed_tenant_sop(db)  # 每公司 SOP 系统数据（上下文已是新公司）
        db.commit()
```

（原本 `db.add(user)` 后直接 `db.commit()`；改为先 `flush` 再播种再 commit。）

- [ ] **Step 5: 移除启动全局 seed** —— `backend/app/main.py` lifespan：删除

```python
    with SessionLocal() as db:
        run_seed(db)
```

三行（连同其上方两行注释）。并删除现已未使用的 `from app.seed import run_seed` import（执行时 `grep -n "run_seed\|SessionLocal" app/main.py` 确认 `SessionLocal` 是否还有其他用途——若无则一并清理该 import）。

- [ ] **Step 6: 跑绿** `.venv/bin/python -m pytest tests/test_sop_tenant_seed.py -v` → PASS。

- [ ] **Step 7: 回归 auth + seed 既有测试** `.venv/bin/python -m pytest tests/test_auth_api.py tests/test_auth_service.py -q` → PASS（注册流程改动）。若有既有 seed 测试 `grep -rl "run_seed" tests/`，一并跑。门禁：`.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app`。

- [ ] **Step 8: Commit**

```bash
git add backend/app/seed.py backend/app/services/auth_service.py backend/app/main.py backend/tests/test_sop_tenant_seed.py
git commit -m "feat(sop): 每公司播种 SOP 系统数据（register 接入）+ 移除启动全局 seed"
```

---

## Task 2: 共享测试 fixture `_sop_auth`

**Files:**
- Modify: `backend/tests/conftest.py`

> 先建好测试基础设施，后续 router 挂闸任务直接用。

- [ ] **Step 1: 加 fixture** —— `backend/tests/conftest.py`，在 `_enterprise_default` 之后追加：

```python
@pytest.fixture
def _sop_auth(_enterprise_default, client, db):  # noqa: PT004
    """SOP 测试登录态：注册一家 enterprise 公司，默认带 token，并设 tenant 上下文。

    - _enterprise_default（before_insert）确保新公司 enterprise → 解锁 sop。
    - client 默认 header 让无 header 的既有 client 调用自动带 token（测试体不动）。
    - 同步设 tenant 上下文：让用 factory 直接 db.add 的行也被盖对 company_id
      （否则直建行 company_id=NULL，被自动过滤后 API 查不到）。
    """
    from app import tenant
    from sqlalchemy import select
    from app.models.company import Company

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "SOPCo",
            "email": "sop@example.com",
            "password": "secret123",
            "name": "Admin",
        },
    )
    token = resp.json()["access_token"]
    company_id = db.execute(select(Company).where(Company.slug == "sopco")).scalar_one().id
    client.headers.update({"Authorization": f"Bearer {token}"})
    ctx = tenant.set_current_company_id(company_id)
    try:
        yield company_id
    finally:
        tenant.reset_current_company_id(ctx)
        client.headers.pop("Authorization", None)
```

> 执行时核实 register 成功响应含 `access_token`（`grep -n "access_token" app/routers/auth.py`）与 slug 生成规则（`SOPCo` → `sopco`，见 `_slugify`）。`# noqa: PT004` 防 flake8-pytest-style 对"无返回 yield fixture"告警——若项目 ruff 未启用 PT 规则可去掉。

- [ ] **Step 2: 自检 fixture 可用** —— 临时验证（用既有任一 SOP 测试在 Task 3 验证；本步仅确保 conftest 语法/导入无误）：`.venv/bin/python -m pytest tests/ -q --co >/dev/null && echo collected-ok`。门禁：`.venv/bin/ruff check tests && .venv/bin/ruff format --check tests`。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test(sop): 共享 _sop_auth fixture（注册+enterprise+默认token+tenant上下文）"
```

---

## Task 3: folders 挂闸 + 迁移 test_folders + feature_gating 单测（确立模式）

**Files:**
- Modify: `backend/app/routers/folders.py:14,28`
- Modify: `backend/tests/integration/test_folders.py`
- Modify: `backend/tests/test_feature_gating.py`

- [ ] **Step 1: feature_gating 加 SOP 锁定单测** —— `backend/tests/test_feature_gating.py`：把 SOP 端点移回。先读当前 `_LOCKED_ENDPOINTS` 段（P6 时标注了"推迟 sop"），把 `/api/v1/folders` 与 `/api/v1/procedures` 加入：

```python
_LOCKED_ENDPOINTS = [
    "/api/v1/preventive-maintenances",
    "/api/v1/purchase-orders",
    "/api/v1/analytics/work-orders",
    "/api/v1/procedures",
    "/api/v1/folders",
]
```

并把 P6 时"sop 推迟"的注释更新为"sop 已挂闸"。

- [ ] **Step 2: 跑红** `.venv/bin/python -m pytest tests/test_feature_gating.py -q -p no:cacheprovider` → `/api/v1/folders`、`/api/v1/procedures` 的 locked_on_free 用例 FAIL（当前未挂闸返回 200/401，非 402）。

- [ ] **Step 3: folders 挂闸** —— `backend/app/routers/folders.py`：

import 区（第 14 行 `from app.deps import RequestMeta, get_db, get_request_meta` 前）加：
```python
from app.billing.catalog import Feature
from app.deps import require_feature
```
（或合并进既有 deps import：`from app.deps import RequestMeta, get_db, get_request_meta, require_feature` + 单独加 `from app.billing.catalog import Feature`，按 ruff isort 顺序。）

router 定义（第 28 行）改为：
```python
router = APIRouter(
    prefix="/api/v1/folders",
    tags=["folders"],
    dependencies=[Depends(require_feature(Feature.sop))],
)
```

- [ ] **Step 4: 跑绿 feature_gating** `.venv/bin/python -m pytest tests/test_feature_gating.py -q -p no:cacheprovider` → procedures 仍 FAIL（下个任务挂），folders 相关 PASS。确认 folders free→402、pro→非402。

- [ ] **Step 5: 跑红 test_folders（挂闸后既有测试 401）** `.venv/bin/python -m pytest tests/integration/test_folders.py -q -p no:cacheprovider` → 大量 401（无 token）。

- [ ] **Step 6: 迁移 test_folders** —— `backend/tests/integration/test_folders.py`：
  (a) 顶部加 `import pytest`（在 `from __future__ import annotations` 后）。
  (b) 加文件级 `pytestmark = pytest.mark.usefixtures("_sop_auth")`（放在 import 之后、首个 `def` 之前）。
  (c) 跑 `.venv/bin/python -m pytest tests/integration/test_folders.py -q -p no:cacheprovider`，逐个修因"每公司自带 废止/归档 两系统文件夹"而失效的断言。常见模式：
     - 列表/树断言"恰好 N 个根文件夹"→ 改为"≥ N"或显式排除 system 文件夹（`[f for f in items if not f["system"]]`）。
     - 文件夹总数计数 +2（系统文件夹）。
     - 首个 code/序号断言通常不受影响（按 prefix 序列）。
  逐条改到该文件 PASS。

> 执行原则：只改因 seed/认证产生的断言偏差，不改业务语义。每改一处即重跑该文件。

- [ ] **Step 7: 门禁** `.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app`。

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/folders.py backend/tests/integration/test_folders.py backend/tests/test_feature_gating.py
git commit -m "feat(sop): folders 挂 feature gate + 迁移 test_folders 至认证态"
```

---

## Task 4: 其余 6 个 SOP router 挂闸

**Files (Modify, 各加 import + router dependencies):**
- `backend/app/routers/procedures.py:16,48`
- `backend/app/routers/procedure_groups.py:13,17`
- `backend/app/routers/nodes.py:10,21`
- `backend/app/routers/parse.py:13,17`
- `backend/app/routers/heading_rules.py:12,21`
- `backend/app/routers/batch_imports.py:16,33`

- [ ] **Step 1: 逐个 router 挂闸** —— 对每个文件做两步（`Depends` 均已从 fastapi import，已确认）：

  (a) import：加 `from app.billing.catalog import Feature`，并补 `require_feature` 到 deps import。各文件 deps import 现状：
   - `procedures` / `procedure_groups`：`from app.deps import RequestMeta, get_db, get_request_meta` → 追加 `, require_feature`
   - `nodes` / `parse` / `heading_rules`：`from app.deps import get_db` → `from app.deps import get_db, require_feature`
   - `batch_imports`：`from app.deps import get_current_user` → `from app.deps import get_current_user, require_feature`

  (b) router 定义加 `dependencies=[Depends(require_feature(Feature.sop))]`：
   - `procedures.py:48` `router = APIRouter(prefix="/api/v1/procedures", tags=["procedures"])`
   - `procedure_groups.py:17` `prefix="/api/v1/procedure-groups", tags=["procedure-groups"]`
   - `nodes.py:21` `router = APIRouter(tags=["nodes"])`（无 prefix）
   - `parse.py:17` `prefix="/api/v1", tags=["parse"]`
   - `heading_rules.py:21` `prefix="/api/v1", tags=["heading-rules"]`
   - `batch_imports.py:33` `prefix="/api/v1/batch-imports", tags=["batch-imports"]`

  统一改为多行形式，例如 procedures：
```python
router = APIRouter(
    prefix="/api/v1/procedures",
    tags=["procedures"],
    dependencies=[Depends(require_feature(Feature.sop))],
)
```
nodes（无 prefix）：
```python
router = APIRouter(
    tags=["nodes"],
    dependencies=[Depends(require_feature(Feature.sop))],
)
```

- [ ] **Step 2: 跑绿 feature_gating** `.venv/bin/python -m pytest tests/test_feature_gating.py -q -p no:cacheprovider` → 全 PASS（procedures 现 402）。

- [ ] **Step 3: 门禁** `.venv/bin/ruff check app && .venv/bin/ruff format --check app && .venv/bin/mypy app` → 净。

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/procedures.py backend/app/routers/procedure_groups.py backend/app/routers/nodes.py backend/app/routers/parse.py backend/app/routers/heading_rules.py backend/app/routers/batch_imports.py
git commit -m "feat(sop): procedures/procedure_groups/nodes/parse/heading_rules/batch_imports 挂 feature gate"
```

---

## Task 5: 迁移其余 SOP integration 测试文件

**Files (Modify):** 9 个文件
- `backend/tests/integration/test_procedures.py`（16）
- `backend/tests/integration/test_nodes_api.py`（4）
- `backend/tests/integration/test_version_management.py`（8）
- `backend/tests/integration/test_editor.py`（2）
- `backend/tests/integration/test_pdf.py`（6）
- `backend/tests/integration/test_word_import.py`（18）
- `backend/tests/integration/test_batch_imports_api.py`（1）
- `backend/tests/integration/test_batch_apply_api.py`（1）
- `backend/tests/integration/test_attachments.py`（6）

> 策略：逐文件迁移，立即跑绿，不堆积。两类文件分别处理。

### A. 纯 client 直调的文件（procedures / nodes_api / version_management / editor / pdf / word_import）

- [ ] **Step 1: 迁移这 6 个文件** —— 对每个：
  (a) 顶部 `from __future__ import annotations` 后加 `import pytest`。
  (b) import 后加 `pytestmark = pytest.mark.usefixtures("_sop_auth")`。
  (c) 若文件用 `factory`（`from tests.conftest import Factory`）直接建 SOP 行：`_sop_auth` 已设 tenant 上下文，factory.add 会自动盖 company_id，通常无需改；但若 factory 在 `_sop_auth` 之前的 fixture 里建行，确认顺序（`_sop_auth` 设上下文应早于 factory 使用——同一测试内 factory 在测试体调用，上下文已设，OK）。
  (d) 逐个跑 `.venv/bin/python -m pytest tests/integration/<file> -q -p no:cacheprovider`，修因 seed 系统文件夹/设置存在而偏差的断言（同 Task 3 Step 6 模式）。

> 已知关注点：`test_procedures.py` 的列表分页/计数断言、`test_version_management.py` 的文件夹相关计数。`test_word_import.py`/`test_pdf.py` 多为内容/转换断言，通常不受 seed 影响，只受认证影响（pytestmark 即解决）。

### B. 自带 bespoke 认证的文件（batch_imports_api / batch_apply_api / attachments）

- [ ] **Step 2: test_batch_imports_api / test_batch_apply_api** —— 这两文件用 `auth_client` fixture（override `get_current_user` 为 fake user，company_id="co-1"）。挂闸后 `require_feature` 会用该 fake user 查 `Company("co-1")` → None → free → 402。修法：让 fake user 的公司存在且为 enterprise。最小改动——在其 `auth_client` fixture 里，override 前先建公司并把 fake user 的 company_id 指向它，且经 `_enterprise_default` 或显式建 enterprise 公司：
  执行时读 `tests/integration/test_batch_imports_api.py` 的 `auth_client` fixture（约 27-35 行），把固定 `company_id="co-1"` 改为：fixture 内用 `db` 建一个 `Company(name="BatchCo", slug="batchco", plan="enterprise", subscription_status="active")`，flush 取 id，fake user 用该 id；并 `tenant.set_current_company_id(that_id)`。两文件共用同一 fixture 则改一处；若各自定义则各改。
  跑 `.venv/bin/python -m pytest tests/integration/test_batch_imports_api.py tests/integration/test_batch_apply_api.py -q -p no:cacheprovider` → PASS。

- [ ] **Step 3: test_attachments** —— 该文件 `_make_procedure(client)` 无 header 建 folder/procedure（挂闸后 401），`_auth(client)` 另注册公司用于 attachment 端点。改法：加 `import pytest` + `pytestmark = pytest.mark.usefixtures("_sop_auth")`，使默认 client 带 token（`_make_procedure` 即可用）；其 attachment 端点本就需认证，默认 header 同样适用。`_auth(client)` 若再注册第二公司会改变默认 header 指向——执行时检查：若某用例依赖 `_auth` 返回的独立 header，确保 attachment 与 procedure 属同一公司（最简：删除 `_auth` 的二次注册，统一用默认 `_sop_auth` 公司）。逐个跑该文件到 PASS。

- [ ] **Step 4: 门禁** `.venv/bin/ruff check tests && .venv/bin/ruff format --check tests`。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration
git commit -m "test(sop): 迁移 SOP integration 测试至认证态（pytestmark _sop_auth + seed 断言微调）"
```

---

## Task 6: 后端全量回归收尾

- [ ] **Step 1: 全量回归** `cd backend && .venv/bin/python -m pytest -q -p no:cacheprovider` → 全绿。若有遗漏 SOP 测试 401/402，按 Task 3/5 模式补 `_sop_auth`。

- [ ] **Step 2: 门禁** `.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app` → 净。

- [ ] **Step 3: 迁移单 head** `.venv/bin/alembic heads` → 仍 `p6_commercialization_gating`（本轮无新迁移）。

- [ ] **Step 4: Commit（如有格式化改动）**

```bash
git add -A backend
git commit -m "chore(sop): 后端全量收尾" || echo "无改动"
```

---

## Task 7: 前端侧边栏 SOP 锁标

**Files:**
- Modify: `frontend/src/components/AppSidebar.vue`
- Modify（如需）: `frontend/tests/unit/AppSidebar.spec.ts`

- [ ] **Step 1: SOP 组加 feature** —— `frontend/src/components/AppSidebar.vue`，`groups` 计算属性里 SOP 组的「程序库/草稿箱/文件夹」加 `feature: 'sop'`（「审计日志」不加）：

```typescript
  {
    label: 'SOP',
    items: [
      { label: '程序库', path: '/procedures/library', feature: 'sop' },
      { label: '草稿箱', path: '/procedures/drafts', feature: 'sop' },
      { label: '文件夹', path: '/folders', feature: 'sop' },
      { label: '审计日志', path: '/audit-logs' },
    ],
  },
```

（`feature`/`isLocked`/`menuIndex` 机制 Task 11 已建，直接复用。）

- [ ] **Step 2: 跑既有 + lock 测试** `cd frontend && npx vitest run tests/unit/AppSidebar.spec.ts tests/unit/components/appSidebarLock.spec.ts` → 全绿。若 AppSidebar.spec 有"SOP 项可点/无锁"的旧断言因 billing 未加载（hasFeature 默认 false → 现在 SOP 判 locked）而失败，按实际：未加载订阅时 `hasFeature` 返回 false，SOP 会显示锁标。修法：该测试若需 SOP 不锁，先在 pinia 里 set `billing.subscription` 含 sop；否则接受锁标为预期，更新断言。

- [ ] **Step 3: 门禁** `npx vue-tsc --noEmit && npx eslint src --max-warnings 0`。仅对改动文件 `npx prettier --check src/components/AppSidebar.vue`（项目 src 存在既有 prettier 漂移，勿全量 --write）。如该文件被自己改动弄乱格式：`npx prettier --write src/components/AppSidebar.vue`（该文件改前合规）。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AppSidebar.vue frontend/tests/unit/AppSidebar.spec.ts
git commit -m "feat(sop): 侧边栏 SOP 模块按 sop feature 显示锁标"
```

---

## Task 8: 前端全量收尾 + 手动验证

- [ ] **Step 1: 前端全量** `cd frontend && npx vitest run` → 全绿。

- [ ] **Step 2: 类型/lint** `npx vue-tsc --noEmit && npx eslint src --max-warnings 0` → 净。

- [ ] **Step 3: 手动端到端验证**（用 `running-smartsop-dev` 技能）：启动 dev → 注册新公司（默认 free）→ 侧边栏 SOP 三项显示锁标、点击跳套餐页；访问 `/api/v1/folders` 返回 402 → 经 platform 端点把该公司设 enterprise → SOP 可访问、自带「废止/归档」文件夹；再注册第二公司确认看不到第一公司的 SOP 数据。记录结论。

- [ ] **Step 4: Commit（如有）**

```bash
git add -A frontend
git commit -m "chore(sop): 前端全量收尾" || echo "无改动"
```

---

## Self-Review（已执行，记录结论）

**Spec 覆盖核对**：
- §组件1 router 挂依赖 → Task 3（folders）+ Task 4（其余6）✓
- §组件2 每公司播种 + 移除启动 seed → Task 1 ✓
- §组件3 前端锁标 → Task 7 ✓
- §组件4 测试改造（fixture + 迁移）→ Task 2（fixture）+ Task 3/5（迁移）✓
- §组件5 单测调整（feature_gating 移回 + 隔离/播种单测）→ Task 3 Step1 + Task 1 ✓
- §无新迁移 / 单 head → Task 6 Step3 ✓
- §验收标准各项 → 分散于 Task 1/3/4/7/8 ✓

**类型/契约一致性**：`require_feature(Feature.sop)` 在 7 router 用同一写法；`_sop_auth` 返回 company_id 供需要者；前端 `feature: 'sop'` 与后端 `Feature.sop` 同字符串。

**已知执行注意**：
1. 测试迁移是主要工作量——seed 系统文件夹使"初始空状态"断言失效，需逐文件跑、按模式微调；bespoke 认证文件（batch*/attachments）单独处理。每迁一个文件即跑绿，不堆积。
2. factory 直建 SOP 行依赖 `_sop_auth` 设的 tenant 上下文盖 company_id——确认 factory 在测试体内（上下文已设）使用。
3. 移除启动 seed 后，dev 环境空库需注册首公司才有 SOP 系统数据（Task 8 手验覆盖）。
```
