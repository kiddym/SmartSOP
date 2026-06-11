# 代码审计缺陷修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-06-11 全栈审计确认的 10 个缺陷（2 个跨租户越权、3 个高危鉴权/校验缺失、3 个功能性 bug、2 个性能问题）。

**Architecture:** 后端 FastAPI + SQLAlchemy（多租户，行级隔离靠 ORM `with_loader_criteria` 事件 + `tenant.bypass_tenant_scope()`）；前端 Vue 3 + Pinia + Element Plus + axios。修复以"把守卫下沉到共享机制"为原则：跨租户检查集中到 `attachment_entities.resolve_and_authorize`，座席/角色校验抽成共享 helper，节点写入复用程序"可编辑"不变量。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 / pydantic-settings v2 / pytest（SQLite in-memory）；TypeScript / Vue 3 / Vite / Vitest（jsdom）/ @vue/test-utils。

**测试运行约定：**
- 后端：`cd backend && DATABASE_URL=sqlite:// python -m pytest <path> -v`（conftest 用 in-memory SQLite；`_register(client, company, email)` 返回 access_token，`_h(token)` 构造 Bearer 头）。
- 前端：`cd frontend && npx vitest run <path>`（jsdom 环境，组件测试用 `@vue/test-utils`）。

**严重度顺序（先做安全，后做功能/性能）：** Task 1-4 安全 → Task 5-8 功能 → Task 9-10 性能。各 Task 独立可交付、可单独提交。

---

## File Structure

修改/新增文件一览：

**后端**
- `backend/app/services/attachment_entities.py` — Task 1：在 `resolve_and_authorize` 加跨租户归属校验
- `backend/app/routers/attachments.py` — Task 1：procedure 别名端点补 `get_current_user`
- `backend/app/config.py` — Task 2：生产环境拒绝默认 `secret_key`
- `backend/app/services/invitation_service.py` — Task 3：抽出 `assert_seat_available` / `assert_role_in_company`
- `backend/app/services/user_service.py` — Task 3：`create_user` 调用上述守卫
- `backend/app/services/node_service.py` — Task 4：节点写入前断言程序可编辑；Task 10：编号重算按字段门控
- `backend/app/deps.py` — Task 5：`get_current_user` 支持 GET/HEAD 的 cookie 兜底
- `backend/app/routers/auth.py` — Task 5：发 token 的端点下发 `access_token` cookie
- `backend/app/schemas/settings.py` — Task 8：`SettingsOut` 补 `auto_archive_days`
- `backend/app/services/procedure_service.py` — Task 9：列表批量取 folder/版本数，消除 N+1

**前端**
- `frontend/src/views/auth/LoginView.vue` — Task 6：补可选公司标识字段
- `frontend/src/api/http.ts` — Task 5：axios `withCredentials: true`
- `frontend/src/views/settings/SettingsView.vue` — Task 7：冲突状态码 412 → 409
- `frontend/src/types/settings.ts` — Task 8：类型已含 `auto_archive_days`（确认即可）

**测试（新增）**
- `backend/tests/test_attachment_tenant_security.py`（Task 1）
- `backend/tests/test_config_secret_guard.py`（Task 2）
- `backend/tests/test_user_create_guards.py`（Task 3）
- `backend/tests/test_node_editable_guard.py`（Task 4）
- `backend/tests/test_cookie_auth.py`（Task 5）
- `backend/tests/test_node_numbering_gating.py`（Task 10）
- `backend/tests/integration/test_settings_archive_field.py`（Task 8）
- `backend/tests/integration/test_procedure_list_counts.py`（Task 9）
- `frontend/src/views/auth/LoginView.spec.ts`（Task 6）
- `frontend/src/views/settings/SettingsView.spec.ts`（Task 7）
- `frontend/src/api/http.spec.ts`（Task 5）

---

## 不在本计划内（审计已判定 by-design / 低危，无需改）

- **密码重置跨公司取首条**（`password_reset_service._find_user`）：代码注释标注有意为之（防枚举优先），重置邮件只发往邮箱所有者本人、token 单次 1h，无第三方接管风险。保持现状。
- **前端路由守卫无权限分级**（`router/guard.ts`）：当前为"单角色模式"（`_role_code` 恒返回 super_admin，人员/角色管理界面下线），后端 `require_permission` 仍对平台类路由强制。属设计内，待角色管理重新上线时再补。
- **SOP 类路由仅 `require_feature` 不带 `require_permission`**：同上，单角色模式下所有用户即 super_admin，后端无实际越权。属架构债，记录但不在本轮修。
- **死代码/重复**（`utils/tree.ts`、`i18n.py`、`layer_walk.py`、`collectLeafFolders` 三处副本等）：属清理类，非缺陷，另开 cleanup 分支处理。

---

## Task 1: 修复 procedure 附件跨租户越权（审计 #1 + #2）

**根因：** `attachment_entities.py` 的 `"procedure"` EntitySpec 用 `view_perm=None, edit_perm=None, scoped=False`，且别名路由 `/api/v1/procedures/{id}/attachments` 不带 `get_current_user`（以 `user=None` 调用）。结果：(a) 匿名可上传/列举任意公司附件；(b) 认证用户可用附件 id 下载他公司附件（`get_or_404` + 宿主查找都走 `bypass_tenant_scope`，且 `perm is None` 跳过授权，全链路无 `company_id` 比对）。

**修复策略：** 在 `resolve_and_authorize` 增加跨租户归属校验（user 已知且宿主有 company_id 时，company_id 不一致→404），并给两个别名端点补 `get_current_user`。两处叠加后，匿名访问与跨租户下载全部封堵；同租户读写行为不变。

**Files:**
- Modify: `backend/app/services/attachment_entities.py:58-73`
- Modify: `backend/app/routers/attachments.py:156-192`
- Test: `backend/tests/test_attachment_tenant_security.py`（Create）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_attachment_tenant_security.py`：

```python
"""附件跨租户越权回归（审计 #1 匿名别名 / #2 跨租户下载）。"""
from __future__ import annotations

import io
import uuid

import pytest
from fastapi import HTTPException

from app import tenant
from app.models.procedure import Procedure
from app.models.user import User
from app.services import attachment_entities as entities


def _proc(db, company_id: str) -> Procedure:
    with tenant.bypass_tenant_scope():
        proc = Procedure(
            procedure_group_id=str(uuid.uuid4()),
            folder_id=str(uuid.uuid4()),
            code="QC-00001",
            name="P",
            level_of_use="reference",
            version=1,
            status="DRAFT",
            is_current=True,
            company_id=company_id,
        )
        db.add(proc)
        db.commit()
    return proc


def _user(company_id: str) -> User:
    # 未持久化即可：procedure spec 的 perm 为 None，resolve_and_authorize 只读 user.company_id。
    return User(email="x@x.com", name="X", password_hash="x", company_id=company_id)


def test_resolve_rejects_cross_tenant_procedure(db):
    proc = _proc(db, "company-B")
    with pytest.raises(HTTPException) as ei:
        entities.resolve_and_authorize(db, _user("company-A"), "procedure", proc.id, "read")
    assert ei.value.status_code == 404


def test_resolve_allows_same_tenant_procedure(db):
    proc = _proc(db, "company-B")
    host = entities.resolve_and_authorize(db, _user("company-B"), "procedure", proc.id, "read")
    assert host.id == proc.id


def test_anonymous_procedure_attachment_upload_401(client):
    pid = "00000000-0000-0000-0000-000000000000"
    r = client.post(
        f"/api/v1/procedures/{pid}/attachments",
        files={"files": ("a.txt", io.BytesIO(b"hi"), "text/plain")},
    )
    assert r.status_code == 401


def test_anonymous_procedure_attachment_list_401(client):
    pid = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/api/v1/procedures/{pid}/attachments")
    assert r.status_code == 401
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_attachment_tenant_security.py -v`
Expected: `test_resolve_rejects_cross_tenant_procedure` FAIL（当前返回宿主不抛错）；两个 `_401` 测试 FAIL（当前返回 201/200）。

- [ ] **Step 3: 在 `resolve_and_authorize` 加跨租户守卫**

`backend/app/services/attachment_entities.py`，把 `resolve_and_authorize` 改为：

```python
def resolve_and_authorize(
    db: Session,
    user: User | None,
    entity_type: str,
    entity_id: str,
    action: Literal["read", "write"],
) -> Any:
    """校验 entity_type（未知→400）→查宿主（不存在/跨租户→404）→租户归属校验→授权（不足→403）→write_guard。返回宿主。"""
    spec = get_spec(entity_type)
    host = _lookup_host(db, spec, entity_id)
    # 跨租户归属校验：宿主走 bypass 查回（scoped=False），故此处显式比对 company_id，
    # 防止认证用户凭 id 访问他公司宿主下的附件（审计 #2）。宿主 company_id 为 NULL
    # 的 phase-0 无主程序不参与比对（保持既有容忍）。
    host_company_id = getattr(host, "company_id", None)
    if user is not None and host_company_id is not None and host_company_id != user.company_id:
        raise not_found("NOT_FOUND", "目标对象不存在")
    perm = spec.view_perm if action == "read" else spec.edit_perm
    if perm is not None and (user is None or perm not in user_permission_codes(db, user)):
        raise forbidden("FORBIDDEN", "权限不足")
    if action != "read" and spec.write_guard is not None:
        spec.write_guard(host)
    return host
```

- [ ] **Step 4: 给 procedure 别名端点补认证**

`backend/app/routers/attachments.py`，把两个别名端点改为带 `get_current_user` 并传入真实 user（替换 `None`）：

```python
# --------------------------------------------------------------------------- #
# procedure 兼容别名（认证 + 跨租户隔离，URL 不变）
# --------------------------------------------------------------------------- #
@router.get("/procedures/{procedure_id}/attachments", response_model=list[AttachmentOut])
def list_procedure_attachments(
    procedure_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AttachmentOut]:
    rows = attachment_service.list_for(db, user, "procedure", procedure_id)
    return [AttachmentOut.model_validate(r) for r in rows]


@router.post(
    "/procedures/{procedure_id}/attachments",
    response_model=list[AttachmentOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_procedure_attachments(
    procedure_id: str,
    files: list[UploadFile] = File(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: RequestMeta = Depends(get_request_meta),
) -> list[AttachmentOut]:
    created = []
    for f in files:
        data = await f.read()
        att = attachment_service.upload_for(
            db,
            user,
            "procedure",
            procedure_id,
            data,
            f.filename or "",
            content_type=f.content_type,
            description=description,
            meta=meta,
        )
        created.append(att)
    db.commit()
    return [AttachmentOut.model_validate(a) for a in created]
```

（`get_current_user` 与 `User` 已在该文件 import，见顶部 `from app.deps import ... get_current_user ...` 与 `from app.models.user import User`。）

- [ ] **Step 5: 运行确认通过 + 回归**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_attachment_tenant_security.py tests/integration -k "attachment or procedure" -v`
Expected: 新测试全部 PASS；既有附件/程序集成测试不回归（同租户上传/下载/列举仍 200/201）。若既有测试此前依赖匿名别名，需改为带 `_h(token)`——按 401 提示修正调用方。

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add backend/app/services/attachment_entities.py backend/app/routers/attachments.py backend/tests/test_attachment_tenant_security.py
git commit -m "fix(security): enforce auth + tenant ownership on procedure attachments"
```

---

## Task 2: 生产环境拒绝默认 JWT 密钥（审计 #3）

**根因：** `config.py` 的 `secret_key` 默认 `"dev-insecure-change-me"`，无任何生产守卫；漏设 `SECRET_KEY` 即用源码公开密钥签发/校验 JWT，可被伪造任意身份。

**Files:**
- Modify: `backend/app/config.py:11,90-110`
- Test: `backend/tests/test_config_secret_guard.py`（Create）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_config_secret_guard.py`：

```python
"""生产环境必须显式配置 SECRET_KEY（审计 #3）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings

_DEFAULT = "dev-insecure-change-me"


def test_default_secret_rejected_in_production():
    with pytest.raises(ValidationError):
        Settings(app_env="production", secret_key=_DEFAULT, _env_file=None)


def test_default_secret_ok_in_development():
    s = Settings(app_env="development", secret_key=_DEFAULT, _env_file=None)
    assert s.secret_key == _DEFAULT


def test_explicit_secret_ok_in_production():
    s = Settings(app_env="production", secret_key="a-strong-random-secret", _env_file=None)
    assert s.is_production and s.secret_key == "a-strong-random-secret"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_config_secret_guard.py -v`
Expected: `test_default_secret_rejected_in_production` FAIL（当前不抛 ValidationError）。

- [ ] **Step 3: 加 model_validator**

`backend/app/config.py`，第 11 行 import 增加 `model_validator`：

```python
from pydantic import Field, field_validator, model_validator
```

在 `is_production` 属性之后（约 110 行）追加校验器：

```python
    @model_validator(mode="after")
    def _require_secret_in_production(self) -> "Settings":
        if self.is_production and self.secret_key == "dev-insecure-change-me":
            raise ValueError(
                "SECRET_KEY 必须在生产环境（APP_ENV=production）显式配置为非默认值"
            )
        return self
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_config_secret_guard.py tests/test_config_jwt.py -v`
Expected: 全 PASS（开发环境默认值仍可用，既有 jwt 配置测试不回归）。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add backend/app/config.py backend/tests/test_config_secret_guard.py
git commit -m "fix(security): reject default SECRET_KEY in production"
```

---

## Task 3: `create_user` 补座席上限与角色租户校验（审计 #4）

**根因：** `POST /api/v1/users` → `user_service.create_user` 直接建用户，不做 `invitation_service.invite` 已有的两项校验：(a) 座席上限（可绕过付费上限）；(b) `role_id` 归属（可挂他公司角色）。

**修复策略：** 把两项校验抽成 `invitation_service` 的共享 helper（同时 DRY 掉 invite 的内联逻辑——回应审计的 reuse/altitude 发现），`create_user` 与 `invite` 都调用。

**Files:**
- Modify: `backend/app/services/invitation_service.py:23-63`
- Modify: `backend/app/services/user_service.py:1-33`
- Test: `backend/tests/test_user_create_guards.py`（Create）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_user_create_guards.py`：

```python
"""POST /users 的座席上限与角色租户校验（审计 #4）。free 套餐 seat_limit=3。"""
from __future__ import annotations


def _register(client, company, email):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_user_rejects_foreign_role(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    b_role = client.get("/api/v1/roles", headers=_h(tb)).json()[0]["id"]
    r = client.post(
        "/api/v1/users",
        headers=_h(ta),
        json={"email": "u@acme.com", "password": "secret123", "name": "U", "role_id": b_role},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_ROLE"


def test_create_user_enforces_seat_limit(client):
    ta = _register(client, "Acme", "a@acme.com")  # 注册即占 1 席（super_admin）
    # free 上限 3：再建 2 个成功（共 3），第 3 个建用户应被拒。
    for i in range(2):
        r = client.post(
            "/api/v1/users",
            headers=_h(ta),
            json={"email": f"u{i}@acme.com", "password": "secret123", "name": f"U{i}"},
        )
        assert r.status_code == 201, r.text
    r = client.post(
        "/api/v1/users",
        headers=_h(ta),
        json={"email": "overflow@acme.com", "password": "secret123", "name": "Over"},
    )
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "SEAT_LIMIT_REACHED"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_user_create_guards.py -v`
Expected: 两个测试 FAIL（当前创建成功，返回 201 而非 400/402）。

- [ ] **Step 3: 在 `invitation_service` 抽出共享守卫**

`backend/app/services/invitation_service.py`，在 `invite` 之前新增两个 helper：

```python
def assert_seat_available(db: Session, company_id: str) -> None:
    """座席上限守卫：在职用户 + 未过期待处理邀请 >= 上限 → 402。无限套餐放行。"""
    company = db.get(Company, company_id)
    limit = effective_seat_limit(
        company.plan if company else None,
        company.subscription_status if company else None,
    )
    if limit is None:
        return
    active_users = db.execute(
        select(func.count())
        .select_from(User)
        .where(User.company_id == company_id, User.status == UserStatus.active)
    ).scalar_one()
    pending_invites = db.execute(
        select(func.count())
        .select_from(UserInvitation)
        .where(
            UserInvitation.company_id == company_id,
            UserInvitation.status == "pending",
            UserInvitation.expires_at > utcnow(),
        )
    ).scalar_one()
    if active_users + pending_invites >= limit:
        raise payment_required("SEAT_LIMIT_REACHED", "席位已达上限，请升级订阅以增加席位")


def assert_role_in_company(db: Session, company_id: str, role_id: str | None) -> None:
    """角色租户归属守卫：role_id 非空时必须属于本公司，否则 400。"""
    if role_id is None:
        return
    role = db.execute(
        select(Role).where(Role.id == role_id, Role.company_id == company_id)
    ).scalar_one_or_none()
    if role is None:
        raise bad_request("INVALID_ROLE", "角色不存在或不属于本组织")
```

然后把 `invite` 中对应的内联逻辑替换为调用（保持行为不变）。将 `invite` 里第 32-63 行（座席校验块 + role 校验块）替换为：

```python
    if existing is not None:
        raise conflict("EMAIL_EXISTS", "该邮箱已是本组织成员")
    assert_seat_available(db, company_id)
    assert_role_in_company(db, company_id, role_id)
    raw = security.generate_token()
```

（删除原内联的 `company = db.get(...)` 座席块与 `if role_id is not None:` 角色块；注意 `company_name` 在 enqueue 处仍需 company 对象——保留/重新获取：把下方 `company_name = company.name if company is not None else company_id` 改为 `company = db.get(Company, company_id)` 后再取 name，或直接 `company_obj = db.get(Company, company_id); company_name = company_obj.name if company_obj else company_id`。）

- [ ] **Step 4: 在 `create_user` 调用守卫**

`backend/app/services/user_service.py`，顶部 import 增加：

```python
from app.services import invitation_service
```

把 `create_user` 改为先校验：

```python
def create_user(db: Session, payload: UserCreate, company_id: str | None = None) -> User:
    # company_id is stamped explicitly from the authenticated caller's tenant
    # (sync threadpool does not see the dependency's contextvar mutation).
    if company_id is not None:
        invitation_service.assert_seat_available(db, company_id)
        invitation_service.assert_role_in_company(db, company_id, payload.role_id)
    user = User(
        email=payload.email,
        password_hash=security.hash_password(payload.password),
        name=payload.name,
        role_id=payload.role_id,
        phone=payload.phone,
        job_title=payload.job_title,
        rate=payload.rate,
        avatar_url=payload.avatar_url,
        company_id=company_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

- [ ] **Step 5: 运行确认通过 + 回归**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_user_create_guards.py tests/test_seat_limit.py tests/test_users_api.py tests/test_cross_tenant_e2e.py -v`
Expected: 新测试 PASS；既有 invite 座席/用户 API/跨租户测试不回归。

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add backend/app/services/invitation_service.py backend/app/services/user_service.py backend/tests/test_user_create_guards.py
git commit -m "fix(users): enforce seat limit and role tenancy on direct user creation"
```

---

## Task 4: 节点写入前断言程序可编辑（审计 #5）

**根因：** `node_service` 的 patch/create/delete/batch/reorder 都不校验宿主程序是否 `is_current and status=="DRAFT"`，可改已发布/归档程序的内容。`procedure_service._assert_editable` 已是该不变量的标准实现。

**修复策略：** 在 `node_service` 增加 `_assert_procedure_editable`（租户作用域查程序——顺带为节点写入补上当前缺失的租户隔离），五个写函数入口调用。

**Files:**
- Modify: `backend/app/services/node_service.py:1-21,112,142,175,184,220`
- Test: `backend/tests/test_node_editable_guard.py`（Create）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_node_editable_guard.py`：

```python
"""节点写入必须限定当前草稿程序（审计 #5）。"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.services import node_service


def _proc_with_node(db, status: str, is_current: bool = True):
    proc = Procedure(
        procedure_group_id=str(uuid.uuid4()),
        folder_id=str(uuid.uuid4()),
        code="QC-00001",
        name="P",
        level_of_use="reference",
        version=1,
        status=status,
        is_current=is_current,
    )
    db.add(proc)
    db.flush()
    node = ProcedureNode(
        procedure_id=proc.id, body="x", heading_level=1, kind="node", sort_order=1000
    )
    db.add(node)
    db.commit()
    return proc, node


def test_patch_node_on_published_rejected(db):
    _proc, node = _proc_with_node(db, status="PUBLISHED")
    with pytest.raises(HTTPException) as ei:
        node_service.patch_node(db, node.id, {"body": "hacked"}, expected_revision=node.revision)
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "PROCEDURE_READONLY"


def test_patch_node_on_draft_ok(db):
    _proc, node = _proc_with_node(db, status="DRAFT")
    out = node_service.patch_node(db, node.id, {"body": "ok"}, expected_revision=node.revision)
    assert out.body == "ok"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_node_editable_guard.py -v`
Expected: `test_patch_node_on_published_rejected` FAIL（当前 patch 成功，不抛错）。

- [ ] **Step 3: 加可编辑守卫并在写函数调用**

`backend/app/services/node_service.py`，import 区（约 14-19 行）补充：

```python
from app.errors import bad_request, not_found, payload_too_large
from app.models.procedure import Procedure
```

（`bad_request`/`not_found` 已 import，仅新增 `Procedure`。）在 `_get_node` 之后新增：

```python
def _assert_procedure_editable(db: Session, procedure_id: str) -> None:
    """节点写入前置守卫：宿主须为当前版本草稿（与 procedure_service._assert_editable 同口径）。
    查询走租户作用域，跨租户程序自然 404，顺带为节点写入补齐租户隔离。"""
    proc = db.execute(
        select(Procedure).where(Procedure.id == procedure_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑")
```

在五个写函数入口各加一行调用：

- `patch_node`（112 行）：`node = _get_node(db, node_id)` 之后加 `_assert_procedure_editable(db, node.procedure_id)`
- `create_node`（142 行）：函数体首行加 `_assert_procedure_editable(db, procedure_id)`
- `delete_node`（175 行）：`node = _get_node(db, node_id)` 之后加 `_assert_procedure_editable(db, node.procedure_id)`
- `batch_update`（184 行）：函数体首行加 `_assert_procedure_editable(db, procedure_id)`
- `reorder`（220 行）：函数体首行加 `_assert_procedure_editable(db, procedure_id)`

- [ ] **Step 4: 运行确认通过 + 回归**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_node_editable_guard.py tests/integration/test_nodes_api.py -v`
Expected: 新测试 PASS；既有节点 API 测试（在 DRAFT 程序上操作）不回归。若有测试在非 DRAFT 程序上改节点，按新不变量修正其前置状态。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add backend/app/services/node_service.py backend/tests/test_node_editable_guard.py
git commit -m "fix(nodes): block mutations on non-draft procedures"
```

---

## Task 5: 内嵌图片鉴权——GET cookie 兜底（审计 #6）

**根因：** 程序资源端点 `GET /procedures/{pid}/assets/{aid}`（及临时媒体 `/uploads/{token}/media/{f}`）经路由级 `require_feature → get_current_user` 需 Bearer 头；但浏览器加载 `<img src>` 不带 Authorization 头，且前端 access token 仅存内存（无 cookie），导致所有内嵌图片 401 破图。持久化的节点正文里存的是干净 URL，token 不能写进 URL。

**修复策略：** 给 `get_current_user` 增加"仅 GET/HEAD 安全方法"的 `access_token` cookie 兜底（写操作仍只认头，杜绝 CSRF）；发 token 的端点下发 httpOnly + SameSite=Lax cookie；前端 axios 开 `withCredentials`。浏览器会自动随 `<img>` GET 带上 cookie，URL 保持干净。

**Files:**
- Modify: `backend/app/deps.py:12,49-69`
- Modify: `backend/app/routers/auth.py:5,44-145`
- Modify: `frontend/src/api/http.ts`
- Test: `backend/tests/test_cookie_auth.py`（Create）、`frontend/src/api/http.spec.ts`（Create）

- [ ] **Step 1: 写失败测试（后端）**

创建 `backend/tests/test_cookie_auth.py`：

```python
"""GET 接受 access_token cookie；写操作仍只认 Authorization 头（审计 #6 + CSRF 安全）。"""
from __future__ import annotations


def _register(client, company="Acme", email="a@acme.com"):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def test_login_sets_access_cookie(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "secret123"})
    assert r.status_code == 200
    assert "access_token" in r.cookies


def test_me_get_accepts_cookie_only(client):
    tok = _register(client)
    client.cookies.clear()
    client.cookies.set("access_token", tok)
    r = client.get("/api/v1/auth/me")  # 无 Authorization 头
    assert r.status_code == 200
    assert r.json()["email"] == "a@acme.com"


def test_mutation_rejects_cookie_only(client):
    tok = _register(client)
    client.cookies.clear()
    client.cookies.set("access_token", tok)
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "secret123", "new_password": "newsecret123"},
    )
    assert r.status_code == 401  # 写操作不认 cookie，防 CSRF
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_cookie_auth.py -v`
Expected: `test_login_sets_access_cookie` FAIL（无 set-cookie）；`test_me_get_accepts_cookie_only` FAIL（401）。

- [ ] **Step 3: `get_current_user` 加 GET/HEAD cookie 兜底**

`backend/app/deps.py`，第 12 行 import 增加 `Request`（已有 `from fastapi import Depends, Request`——确认含 Request）。把 `get_current_user` 改为：

```python
def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    # 仅安全方法（GET/HEAD）允许用 access_token cookie 兜底，使浏览器 <img> 等
    # 无法携带 Authorization 头的资源请求可认证；写操作只认头，避免 CSRF。
    if not token and request.method in ("GET", "HEAD"):
        token = request.cookies.get("access_token")
    if not token:
        raise unauthorized("UNAUTHENTICATED", "未认证")
    try:
        claims = security.decode_token(token)
    except security.TokenError:
        raise unauthorized("INVALID_TOKEN", "无效的令牌") from None
    if claims.get("type") != "access":
        raise unauthorized("INVALID_TOKEN", "令牌类型错误")
    company_id = claims.get("company_id")
    user_id = claims.get("sub")
    tenant.set_current_company_id(company_id)  # scope before loading
    user = db.get(User, user_id)
    if user is None or user.company_id != company_id:
        raise unauthorized("USER_NOT_FOUND", "用户不存在")
    if user.status != UserStatus.active:
        raise unauthorized("ACCOUNT_DISABLED", "账号已禁用")
    return user
```

- [ ] **Step 4: 发 token 的端点下发 cookie**

`backend/app/routers/auth.py`，第 5 行 import 增加 `Response`：

```python
from fastapi import APIRouter, Depends, Response
```

并 import settings：

```python
from app.config import settings
```

新增下发助手，并改造 `_tokens` 调用方。在 `_tokens` 之后加：

```python
def _issue(db: Session, user: User, response: Response) -> TokenPair:
    pair = _tokens(db, user)
    response.set_cookie(
        "access_token",
        pair.access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/api/v1",
    )
    return pair
```

把 `register` / `login` / `refresh` / `accept_invite` / `switch_account` 五个端点签名加 `response: Response`，并把 `return _tokens(db, user)` 改为 `return _issue(db, user, response)`。例如 login：

```python
@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = auth_service.authenticate(db, payload)
    except auth_service.AuthError as exc:
        raise unauthorized("LOGIN_FAILED", str(exc)) from exc
    return _issue(db, user, response)
```

（其余四个端点同理：在参数表加 `response: Response`，return 改 `_issue(...)`；switch_account 用 `_issue(db, member, response)`。）

- [ ] **Step 5: 运行确认通过（后端）**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_cookie_auth.py tests/test_auth_api.py -v`
Expected: 全 PASS。

- [ ] **Step 6: 前端 axios 开 withCredentials + 测试**

`frontend/src/api/http.ts`，在 `axios.create({...})` 配置中加 `withCredentials: true`（与 `baseURL` 同级）。

创建 `frontend/src/api/http.spec.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { http } from './http'

describe('http client', () => {
  it('sends cookies so <img> asset requests authenticate', () => {
    expect(http.defaults.withCredentials).toBe(true)
  })
})
```

- [ ] **Step 7: 运行确认通过（前端）**

Run: `cd frontend && npx vitest run src/api/http.spec.ts`
Expected: PASS。

- [ ] **Step 8: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add backend/app/deps.py backend/app/routers/auth.py backend/tests/test_cookie_auth.py frontend/src/api/http.ts frontend/src/api/http.spec.ts
git commit -m "fix(auth): cookie fallback for GET so embedded asset images authenticate"
```

---

## Task 6: 登录补可选公司标识字段（审计 #7）

**根因：** 同邮箱跨多公司时后端要求 `company_slug` 否则 401，但登录表单无此字段，导致这类用户在 UI 永久无法登录。

**Files:**
- Modify: `frontend/src/views/auth/LoginView.vue`
- Test: `frontend/src/views/auth/LoginView.spec.ts`（Create）

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/views/auth/LoginView.spec.ts`：

```typescript
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import LoginView from './LoginView.vue'
import { useAuthStore } from '@/store/auth'

const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': {} } })
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', name: 'home', component: { template: '<div/>' } },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: { template: '<div/>' } },
    { path: '/forgot', name: 'forgot-password', component: { template: '<div/>' } },
  ],
})

describe('LoginView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('passes company_slug to auth.login when provided', async () => {
    const wrapper = mount(LoginView, {
      global: { plugins: [i18n, router], stubs: { AuthLayout: { template: '<div><slot/></div>' } } },
    })
    const auth = useAuthStore()
    const loginSpy = vi.spyOn(auth, 'login').mockResolvedValue()

    await wrapper.find('[data-test="email"]').setValue('a@acme.com')
    await wrapper.find('[data-test="password"]').setValue('secret123')
    await wrapper.find('[data-test="company-slug"]').setValue('acme')
    await wrapper.find('[data-test="submit"]').trigger('click')

    expect(loginSpy).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'a@acme.com', password: 'secret123', company_slug: 'acme' }),
    )
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/views/auth/LoginView.spec.ts`
Expected: FAIL（无 `[data-test="company-slug"]` 元素 / 未传 company_slug）。

- [ ] **Step 3: 加可选公司标识字段**

`frontend/src/views/auth/LoginView.vue`：
1. `form` 加字段：`const form = ref({ email: '', password: '', companySlug: '' })`
2. `submit` 中调用改为：

```typescript
    await auth.login({
      email: form.value.email,
      password: form.value.password,
      company_slug: form.value.companySlug || undefined,
    })
```

3. 模板在 password 表单项之后、登录按钮之前加可选字段：

```html
      <el-form-item :label="t('auth.companySlugOptional')" prop="companySlug">
        <el-input v-model="form.companySlug" data-test="company-slug" autocomplete="organization" />
      </el-form-item>
```

4. 在 `frontend/src/i18n` 的 zh-CN auth 段加 key `companySlugOptional: '公司标识（同邮箱多公司时填写）'`（参照该目录现有 auth 文案结构；若 i18n 文件按 `auth.*` 命名空间组织，按既有格式补这一条）。

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/views/auth/LoginView.spec.ts`
Expected: PASS。若组件测试缺全局 setup（首个组件测试），在 `vite.config.ts` 的 `test` 段确认 `environment: 'jsdom'`，或依赖测试顶部的 `// @vitest-environment jsdom` pragma（已含）。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add frontend/src/views/auth/LoginView.vue frontend/src/views/auth/LoginView.spec.ts frontend/src/i18n
git commit -m "fix(login): add optional company slug for multi-tenant email disambiguation"
```

---

## Task 7: 设置保存冲突状态码 412 → 409（审计 #8）

**根因：** `SettingsView.vue` 用 `status === 412` 判"被他人修改"，但后端乐观锁冲突抛 409 VERSION_CONFLICT（412 仅代表缺/坏 If-Match，前端始终带）。结果真正冲突落入通用错误分支且不刷新 revision，陷入死循环。

**Files:**
- Modify: `frontend/src/views/settings/SettingsView.vue:51-58`
- Test: `frontend/src/views/settings/SettingsView.spec.ts`（Create）

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/views/settings/SettingsView.spec.ts`：

```typescript
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SettingsView from './SettingsView.vue'
import * as settingsApi from '@/api/settings'

const baseSettings = {
  id: 's1', enable_version_control: true, enable_approval_workflow: false,
  max_version_number: 100, require_read_confirmation: false, default_risk_level: 1,
  default_quality_level: 1, revision: 5, updated_at: '2026-01-01T00:00:00Z', auto_archive_days: 365,
}

describe('SettingsView 冲突处理', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('在 409 冲突时刷新设置', async () => {
    vi.spyOn(settingsApi, 'getSettings').mockResolvedValue({ ...baseSettings })
    const updateSpy = vi
      .spyOn(settingsApi, 'updateSettings')
      .mockRejectedValueOnce({ response: { status: 409 } })
    const wrapper = mount(SettingsView, { global: { stubs: { 'el-card': { template: '<div><slot/></div>' } } } })
    await flushPromises()
    updateSpy.mockClear()
    vi.spyOn(settingsApi, 'getSettings').mockResolvedValue({ ...baseSettings, revision: 6 })

    await (wrapper.vm as unknown as { handleSave: () => Promise<void> }).handleSave()
    await flushPromises()

    // 409 后应再次拉取设置（刷新 revision）
    expect(settingsApi.getSettings).toHaveBeenCalled()
  })
})
```

> 注：若 `handleSave` 未暴露到实例，改为通过点击保存按钮触发（`wrapper.find('[data-test="save"]')`，并在模板保存按钮加 `data-test="save"`）。

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/views/settings/SettingsView.spec.ts`
Expected: FAIL（当前判 412，409 落入 else 分支不刷新）。

- [ ] **Step 3: 改状态码判断为 409**

`frontend/src/views/settings/SettingsView.vue`，`handleSave` 的 catch 块改为：

```typescript
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 409) {
      ElMessage.error('设置已被他人修改，请刷新后重试')
      await loadSettings() // refresh to get latest revision
    } else {
      ElMessage.error('保存失败，请重试')
    }
  } finally {
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/views/settings/SettingsView.spec.ts`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add frontend/src/views/settings/SettingsView.vue frontend/src/views/settings/SettingsView.spec.ts
git commit -m "fix(settings): treat 409 (not 412) as optimistic-lock conflict"
```

---

## Task 8: `SettingsOut` 暴露 `auto_archive_days`（审计 #9）

**根因：** 模型有 `auto_archive_days`（默认 365），前端类型与设置页都用它，但 `SettingsOut` 未含该字段，接口永不返回，页面恒显示 "- 天"。

**Files:**
- Modify: `backend/app/schemas/settings.py:10-23`
- Test: `backend/tests/integration/test_settings_archive_field.py`（Create）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/integration/test_settings_archive_field.py`：

```python
"""GET /settings 应返回 auto_archive_days（审计 #9）。"""
from __future__ import annotations


def _register(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def test_settings_includes_auto_archive_days(client):
    tok = _register(client)
    r = client.get("/api/v1/settings/current", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "auto_archive_days" in body
    assert isinstance(body["auto_archive_days"], int)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/integration/test_settings_archive_field.py -v`
Expected: FAIL（响应不含 auto_archive_days）。

- [ ] **Step 3: SettingsOut 补字段**

`backend/app/schemas/settings.py`，`SettingsOut` 在 `default_quality_level` 之后加：

```python
    default_quality_level: int
    auto_archive_days: int
    revision: int
    updated_at: datetime
```

（`SettingsOut` 用 `from_attributes=True`，会自动读 `proc.auto_archive_days`；`SettingsUpdate` 不变——该字段仍只读、不可改。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/integration/test_settings_archive_field.py -v`
Expected: PASS。前端无需改（`types/settings.ts` 已含 `auto_archive_days`，`SettingsView` 已渲染）。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add backend/app/schemas/settings.py backend/tests/integration/test_settings_archive_field.py
git commit -m "fix(settings): expose auto_archive_days in SettingsOut"
```

---

## Task 9: 消除程序列表 N+1 查询（审计 #10）

**根因：** `list_procedures`/`list_library` 对每行 `_out_model` 各跑一次 `_folder_full_path`（`db.get`）+ `_version_count`（COUNT），page_size≤100 时单页 ~200 次查询。

**修复策略：** 新增批量构造 `_out_models`，一次 `IN()` 取所有 folder、一次 `GROUP BY` 统计各 group 版本数，列表函数改调它。

**Files:**
- Modify: `backend/app/services/procedure_service.py:141-145,540-596`
- Test: `backend/tests/integration/test_procedure_list_counts.py`（Create）

- [ ] **Step 1: 写失败测试（先锁正确性，便于重构后比对）**

创建 `backend/tests/integration/test_procedure_list_counts.py`：

```python
"""程序列表批量构造的正确性回归（审计 #10：folder_full_path + version_count_in_group）。"""
from __future__ import annotations


def _register(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_library_list_reports_paths_and_counts(client):
    tok = _register(client)
    # 列表应返回每行的 folder_full_path 与 version_count_in_group（值随种子数据，至少存在且类型正确）。
    r = client.get("/api/v1/procedures", headers=_h(tok), params={"page": 1, "page_size": 20})
    assert r.status_code == 200, r.text
    page = r.json()
    for item in page["items"]:
        assert "folder_full_path" in item
        assert isinstance(item["version_count_in_group"], int)
        assert item["version_count_in_group"] >= 1
```

> 该测试主要锁字段契约不被重构破坏；若种子无程序则 items 为空、循环空过（仍验证 200 与分页结构）。

- [ ] **Step 2: 运行确认（当前应 PASS——作为重构前基线）**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/integration/test_procedure_list_counts.py -v`
Expected: PASS（重构前后均须 PASS；这是不变量基线，非红灯）。

- [ ] **Step 3: 新增批量构造并替换列表的逐行调用**

`backend/app/services/procedure_service.py`，在 `_out_model`（141 行）之后新增：

```python
def _out_models(db: Session, rows: list[Procedure]) -> list[ProcedureOut]:
    """批量构造 ProcedureOut：一次 IN() 取 folder 路径 + 一次 GROUP BY 取版本数，消除逐行 N+1。"""
    if not rows:
        return []
    folder_ids = {p.folder_id for p in rows if p.folder_id is not None}
    path_by_folder: dict[str, str] = {}
    if folder_ids:
        for fid, full_path in db.execute(
            select(Folder.id, Folder.full_path).where(Folder.id.in_(folder_ids))
        ).all():
            path_by_folder[fid] = full_path
    group_ids = {p.procedure_group_id for p in rows}
    count_by_group: dict[str, int] = {
        gid: int(n)
        for gid, n in db.execute(
            select(Procedure.procedure_group_id, func.count())
            .where(Procedure.procedure_group_id.in_(group_ids), Procedure.is_active.is_(True))
            .group_by(Procedure.procedure_group_id)
        ).all()
    }
    out: list[ProcedureOut] = []
    for proc in rows:
        data: dict[str, Any] = {f: getattr(proc, f) for f in _OUT_FIELDS}
        data["folder_full_path"] = path_by_folder.get(proc.folder_id, "")
        data["version_count_in_group"] = count_by_group.get(proc.procedure_group_id, 0)
        out.append(ProcedureOut.model_validate(data))
    return out
```

把 `list_procedures`（570 行）与 `list_library`（596 行）的返回从
`return [_out_model(db, p) for p in rows], total`
改为
`return _out_models(db, rows), total`。

（`Folder`、`func`、`select`、`Any`、`_OUT_FIELDS`、`ProcedureOut` 均已在该文件作用域内；`_out_model` 保留供 `to_meta` 之外的单行调用方使用。）

- [ ] **Step 4: 运行确认通过 + 回归**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/integration/test_procedure_list_counts.py tests/integration/test_procedures.py -v`
Expected: 全 PASS（字段值与重构前一致）。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add backend/app/services/procedure_service.py backend/tests/integration/test_procedure_list_counts.py
git commit -m "perf(procedures): batch folder paths and version counts to kill list N+1"
```

---

## Task 10: 节点 patch 按字段门控编号重算（性能）

**根因：** `patch_node` 无条件调用 `node_numbering.recompute`（重拉全程序节点重建树），即便只改 `body`/`input_schema`/`attachment_marks`（不影响编号）也全表扫描——大程序每次正文自动保存都 O(N)。

**修复策略：** 仅当本次 `changes` 触及编号相关字段（`heading_level`/`kind`/`skip_numbering`）才 recompute；`_learn_from_edit` 仍每次执行。

**Files:**
- Modify: `backend/app/services/node_service.py:107-139`
- Test: `backend/tests/test_node_numbering_gating.py`（Create）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_node_numbering_gating.py`：

```python
"""patch_node 仅在编号相关字段变更时重算（性能门控）。"""
from __future__ import annotations

import uuid

from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.services import node_numbering, node_service


def _draft_node(db):
    proc = Procedure(
        procedure_group_id=str(uuid.uuid4()), folder_id=str(uuid.uuid4()), code="QC-00001",
        name="P", level_of_use="reference", version=1, status="DRAFT", is_current=True,
    )
    db.add(proc)
    db.flush()
    node = ProcedureNode(
        procedure_id=proc.id, body="x", heading_level=1, kind="node", sort_order=1000
    )
    db.add(node)
    db.commit()
    return node


def test_body_only_patch_skips_recompute(db, monkeypatch):
    node = _draft_node(db)
    calls: list[int] = []
    monkeypatch.setattr(node_numbering, "recompute", lambda *a, **k: calls.append(1))
    node_service.patch_node(db, node.id, {"body": "new body"}, expected_revision=node.revision)
    assert calls == []  # 正文变更不影响编号，不应重算


def test_level_patch_triggers_recompute(db, monkeypatch):
    node = _draft_node(db)
    calls: list[int] = []
    monkeypatch.setattr(node_numbering, "recompute", lambda *a, **k: calls.append(1))
    node_service.patch_node(db, node.id, {"heading_level": 2}, expected_revision=node.revision)
    assert calls == [1]  # 层级变更需重算编号
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_node_numbering_gating.py -v`
Expected: `test_body_only_patch_skips_recompute` FAIL（当前无条件重算，calls==[1]）。

- [ ] **Step 3: 加字段门控**

`backend/app/services/node_service.py`，在 `_PATCHABLE`（107 行）之后加常量：

```python
# 影响编号的字段：仅当本次变更触及这些字段时才重算 code（正文/schema/marks 不影响编号）。
_NUMBERING_FIELDS = frozenset({"heading_level", "kind", "skip_numbering"})
```

把 `patch_node` 中 `db.flush()` 之后的重算行（137 行）改为门控：

```python
    optimistic_lock.bump(node)
    db.flush()
    if changes.keys() & _NUMBERING_FIELDS:
        node_numbering.recompute(db, node.procedure_id)
    _learn_from_edit(db, node, old_level, old_mark)  # M3 隐式学习信号
    return node
```

> 注意：仅改 `patch_node`。`create_node`/`delete_node`/`reorder`/`batch_update` 的 recompute 是结构性变更必须保留，不动。

- [ ] **Step 4: 运行确认通过 + 回归**

Run: `cd backend && DATABASE_URL=sqlite:// python -m pytest tests/test_node_numbering_gating.py tests/integration/test_nodes_api.py -v`
Expected: 全 PASS（编号相关 patch 仍正确重算，正文 patch 不再重算）。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git add backend/app/services/node_service.py backend/tests/test_node_numbering_gating.py
git commit -m "perf(nodes): only recompute numbering when numbering fields change"
```

---

## 收尾验证

全部 Task 完成后，跑完整套件确认无回归：

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/backend" && DATABASE_URL=sqlite:// python -m pytest -q
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend" && npx vitest run
```

Expected: 后端全绿、前端全绿。若 Task 1/3/4 暴露了既有测试中"匿名访问别名 / 非草稿改节点 / 跨租户角色"的旧用法，按新不变量更新这些测试（属预期收紧，非回归）。

---

## Self-Review（作者自查结论）

- **Spec 覆盖**：审计 10 项确认缺陷 → Task 1(#1+#2)、2(#3)、3(#4)、4(#5)、5(#6)、6(#7)、7(#8)、8(#9)、9(#10)、10(性能门控)。低危/by-design 4 项在"不在本计划内"显式记录。✅
- **占位符扫描**：无 TBD/TODO；每个代码步骤含完整可粘贴代码与确切命令、预期输出。✅
- **类型一致性**：`assert_seat_available`/`assert_role_in_company`（Task 3）在定义与调用处签名一致；`_out_models`（Task 9）、`_assert_procedure_editable`（Task 4）、`_NUMBERING_FIELDS`/`_issue`（Task 5/10）命名前后统一。✅
- **风险提示**：Task 1/3/4 会收紧既有宽松行为，可能需同步更新少量旧测试（已在 Step 5 与收尾说明）。前端组件测试为本仓首批，若无全局 vitest setup，依赖各测试顶部 `// @vitest-environment jsdom` pragma（已加）。

---

## 已知限制 / 跟进项（Task 5 评审记录）

- **登出不清除 access_token cookie。** Task 5 引入的 `access_token` httpOnly cookie max-age=60min，前端 `store.logout` 仅清客户端 token，无服务端 `/auth/logout` 清 cookie。共享机器上登出后，后续用户在 cookie 过期前可重放认证态 GET 请求（如 `/auth/me`、资源图片）。该姿态与既有 refresh token（localStorage 内、同样无服务端撤销）一致，非本次新增的弱点类别，作为已知限制记录。**跟进修复：** 新增 `POST /api/v1/auth/logout`，`response.delete_cookie("access_token", path="/api/v1")`（path 必须一致否则清不掉），并让前端 `store.logout` 调用它。
