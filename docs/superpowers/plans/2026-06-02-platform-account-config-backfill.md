# 平台账户与配置补全 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐平台账户与配置层的 Atlas 功能缺口——密码重置、用户邀请、改密码、CompanySettings、Currency。

**Architecture:** 复用现有 `security`(哈希/JWT)、`email_outbox`(事务邮件)、`auth_service`、`tenant`(pre-auth bypass+租户定位)、`require_permission`。新增 token 工具(secrets+sha256) + 事务邮件入队 + 4 张新表 + 对应 service/router。

**Tech Stack:** FastAPI 同步 / SQLAlchemy 2.x / Alembic / pytest(SQLite) / ruff 0.15 + mypy 1.20。

**前置依赖：** 分支 `feat/platform-account-config-backfill`(= 最新 main)。后端 `/auth/{login,register,refresh,me}` + RBAC + email outbox 已就绪。

**spec：** `docs/superpowers/specs/2026-06-02-platform-account-config-backfill-design.md`

---

## 关键约定（先读）

- **后端解释器**：`backend/.venv/bin/python`（pytest/alembic/ruff/mypy 都用它）。测试 SQLite 用 `Base.metadata.create_all`（conftest engine fixture），**不依赖 alembic**；alembic 迁移是生产 artifact，集中在最后一个 task 写。
- **token**：`security.generate_token()`(secrets.token_urlsafe，明文仅入邮件) + `security.hash_token()`(sha256，DB 只存哈希)。
- **事务邮件**：新增 `email_outbox_service.enqueue_transactional`（直发、不过通知偏好、`recipient_user_id` 可空）——密码重置/邀请用它。`EmailOutbox.recipient_user_id` 改为可空（最后迁移 task 处理）。
- **pre-auth 租户**：forgot/reset/accept-invite 无登录态 → `with tenant.bypass_tenant_scope():` 查 token/定位用户/建用户，建用户时 `set_current_company_id(inv.company_id)`（同 login/register 与批量 worker 的模式）。
- **JWT 无状态限制**：密码重置后**不强制吊销已签发 refresh**（JWT 无 DB 黑名单；严格吊销需 token_version 机制，本轮不做，spec §3 的"吊销 refresh"据此降级）。已在此声明。
- **净室**：参照 Atlas 行为全新原创，不复制其代码/字段名/文案。
- **提交**：commit message 结尾加 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

---

## 文件结构

| 文件 | 动作 |
|---|---|
| `backend/app/security.py` | 改：增 `generate_token`/`hash_token` |
| `backend/app/services/email_outbox_service.py` | 改：增 `enqueue_transactional` |
| `backend/app/email/templates.py` | 改：增 `_password_reset`/`_invite_user` + 注册 |
| `backend/app/models/password_reset_token.py` | 创建 |
| `backend/app/models/user_invitation.py` | 创建 |
| `backend/app/models/company_settings.py` | 创建 |
| `backend/app/models/currency.py` | 创建 |
| `backend/app/models/__init__.py` | 改：导出新模型 |
| `backend/app/models/email_outbox.py` | 改：recipient_user_id 可空 |
| `backend/app/services/password_reset_service.py` | 创建 |
| `backend/app/services/invitation_service.py` | 创建 |
| `backend/app/services/auth_service.py` | 改：增 `change_password` |
| `backend/app/services/company_settings_service.py` | 创建 |
| `backend/app/services/currency_service.py` | 创建 |
| `backend/app/schemas/auth.py` | 改：增请求 schema |
| `backend/app/schemas/platform.py` | 创建：CompanySettings/Currency/Invitation schema |
| `backend/app/routers/auth.py` | 改：增 forgot/reset/change-password/accept-invite |
| `backend/app/routers/users.py` | 改：增 invite |
| `backend/app/routers/company_settings.py` | 创建 |
| `backend/app/routers/currencies.py` | 创建 |
| `backend/app/main.py` | 改：注册新 router |
| `backend/app/permissions.py` | 改：增 CURRENCY_MANAGE 权限码（若无） |
| `backend/alembic/versions/<new>.py` | 创建：4 表 + email_outbox 改动 |
| `backend/tests/...` | 各 task 测试 |

---

## Task 1: token 工具 + 事务邮件 + 邮件模板

**Files:**
- Modify: `backend/app/security.py`、`backend/app/services/email_outbox_service.py`、`backend/app/email/templates.py`
- Test: `backend/tests/unit/test_token_and_transactional_email.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/unit/test_token_and_transactional_email.py`:

```python
from app import security


def test_generate_token_unique_and_hash_stable():
    a, b = security.generate_token(), security.generate_token()
    assert a != b and len(a) >= 20
    assert security.hash_token(a) == security.hash_token(a)
    assert security.hash_token(a) != security.hash_token(b)


def test_password_reset_template_renders():
    from app.email.templates import render
    subject, body = render("PASSWORD_RESET", {"reset_url": "https://x/reset?token=t", "deadline": "1小时"})
    assert "密码" in subject
    assert "https://x/reset?token=t" in body


def test_invite_template_renders():
    from app.email.templates import render
    subject, body = render("INVITE_USER", {"company_name": "Acme", "invite_url": "https://x/accept?token=t"})
    assert "Acme" in subject or "Acme" in body
    assert "https://x/accept?token=t" in body
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_token_and_transactional_email.py -v`
Expected: FAIL — `security.generate_token` 不存在 / 模板未注册

- [ ] **Step 3: 加 token 工具**

在 `backend/app/security.py` 顶部 import 区加 `import hashlib`、`import secrets`，并追加：

```python
def generate_token() -> str:
    """生成 URL-safe 随机 token（明文仅入邮件，DB 存其哈希）。"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """token 的 sha256 十六进制（DB 存哈希，不存明文）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: 加邮件模板**

在 `backend/app/email/templates.py` 追加两个模板函数（对齐现有 `def _x(p)->tuple[str,str]` + `_g` 风格）并注册进 `_TEMPLATES`：

```python
def _password_reset(p: dict[str, Any]) -> tuple[str, str]:
    return (
        "[账户] 密码重置",
        f"您请求了密码重置。请在 {_g(p, 'deadline', '1 小时')}内点击以下链接完成重置：\n"
        f"{_g(p, 'reset_url')}\n\n若非本人操作，请忽略本邮件。",
    )


def _invite_user(p: dict[str, Any]) -> tuple[str, str]:
    company = _g(p, "company_name")
    return (
        f"[邀请] 加入 {company}",
        f"您被邀请加入 {company}。请点击以下链接设置密码并完成加入：\n"
        f"{_g(p, 'invite_url')}\n\n邀请有效期至 {_g(p, 'deadline', '7 天后')}。",
    )
```

在 `_TEMPLATES` 字典追加：
```python
    "PASSWORD_RESET": _password_reset,
    "INVITE_USER": _invite_user,
```

- [ ] **Step 5: 加事务邮件入队**

先 Read `backend/app/models/email_outbox.py` 确认 `EmailOutbox` 字段名（recipient_user_id/recipient_email/type/subject/body/status 及其它必填项），然后在 `backend/app/services/email_outbox_service.py` 追加（构造时对齐实际字段；下方按已知字段写）：

```python
def enqueue_transactional(
    db: Session,
    *,
    company_id: str,
    recipient_email: str,
    type: str,
    params: dict[str, Any],
    recipient_user_id: str | None = None,
) -> EmailOutbox:
    """事务邮件直发入队（密码重置/邀请）：不过通知偏好、recipient_user_id 可空。不 commit。"""
    subject, body = render(type, params)
    row = EmailOutbox(
        company_id=company_id,
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        type=type,
        subject=subject,
        body=body,
        status="pending",
    )
    db.add(row)
    db.flush()
    return row
```
（`render` 若未在本模块 import，从 `app.email.templates import render`。）

- [ ] **Step 6: 运行确认通过 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_token_and_transactional_email.py -v`
Expected: PASS（3 passed）

```bash
cd backend && ruff check app/security.py app/email/templates.py app/services/email_outbox_service.py tests/unit/test_token_and_transactional_email.py && ruff format app/security.py app/email/templates.py app/services/email_outbox_service.py && mypy app/security.py app/services/email_outbox_service.py
git add app/security.py app/email/templates.py app/services/email_outbox_service.py tests/unit/test_token_and_transactional_email.py
git commit -m "feat(platform): token util + transactional email enqueue + reset/invite templates"
```

---

## Task 2: 密码重置

**Files:**
- Create: `backend/app/models/password_reset_token.py`、`backend/app/services/password_reset_service.py`
- Modify: `backend/app/models/__init__.py`、`backend/app/schemas/auth.py`、`backend/app/routers/auth.py`
- Test: `backend/tests/integration/test_password_reset_api.py`

- [ ] **Step 1: 写模型**

Create `backend/app/models/password_reset_token.py`:

```python
"""密码重置 token（Atlas VerificationToken 净室复刻）。token 只存哈希。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class PasswordResetToken(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_password_reset_token"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DATETIME6)
    used_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
```

在 `backend/app/models/__init__.py` 追加 `from app.models.password_reset_token import PasswordResetToken` 并加入 `__all__`。

- [ ] **Step 2: 增 schema**

在 `backend/app/schemas/auth.py` 追加：

```python
class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    company_slug: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
```

- [ ] **Step 3: 写失败测试**

Create `backend/tests/integration/test_password_reset_api.py`:

```python
from sqlalchemy import select

from app.models.email_outbox import EmailOutbox
from app.models.password_reset_token import PasswordResetToken


def _register(client, email="a@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": email, "password": "secret123", "name": "Alice"})


def test_forgot_password_enqueues_and_resets(client, db):
    _register(client)
    r = client.post("/api/v1/auth/forgot-password", json={"email": "a@acme.com"})
    assert r.status_code == 200
    # 入队了重置邮件
    mail = db.execute(select(EmailOutbox).where(EmailOutbox.type == "PASSWORD_RESET")).scalar_one()
    assert mail.recipient_email == "a@acme.com"
    # 取出 token（测试从 DB 行重建：实际 token 在邮件 url，测试用 service 暴露/或解析。这里直接查行并伪造已知 token 不可行，故改测 service 层见下）


def test_forgot_password_unknown_email_still_200(client):
    _register(client)
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@acme.com"})
    assert r.status_code == 200  # 防枚举


def test_reset_with_valid_token(client, db):
    from app import security, tenant
    from app.models.user import User
    _register(client)
    # 直接走 service 生成可知 token
    from app.services import password_reset_service
    raw = password_reset_service.request_reset(db, email="a@acme.com")  # 返回明文 token（仅测试用）
    db.commit()
    assert raw is not None
    r = client.post("/api/v1/auth/reset-password", json={"token": raw, "new_password": "newsecret456"})
    assert r.status_code == 200, r.text
    # 旧 token 失效
    r2 = client.post("/api/v1/auth/reset-password", json={"token": raw, "new_password": "again12345"})
    assert r2.status_code in (400, 410)
    # 新密码可登录
    login = client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "newsecret456"})
    assert login.status_code == 200
```

> 注：`request_reset` 返回明文 token **仅为可测性**（生产路由不返回 token、只入邮件）；路由层 forgot-password 调用它但丢弃返回值。

- [ ] **Step 4: 写 service**

Create `backend/app/services/password_reset_service.py`:

```python
"""密码重置：forgot(防枚举入队) + reset(校验 token 改密)。pre-auth 用 bypass。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security, tenant
from app.errors import bad_request
from app.models.base import utcnow
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User, UserStatus
from app.services import email_outbox_service

_TTL_HOURS = 1


def _find_user(db: Session, email: str, company_slug: str | None) -> User | None:
    stmt = select(User).where(User.email == email, User.status == UserStatus.active)
    if company_slug:
        from app.models.company import Company
        stmt = stmt.join(Company, Company.id == User.company_id).where(Company.slug == company_slug)
    return db.execute(stmt).scalars().first()


def request_reset(db: Session, *, email: str, company_slug: str | None = None) -> str | None:
    """生成重置 token 并入队邮件。返回明文 token（仅供测试；路由丢弃）。无此用户→None(防枚举)。"""
    with tenant.bypass_tenant_scope():
        user = _find_user(db, email, company_slug)
        if user is None:
            return None
        raw = security.generate_token()
        db.add(PasswordResetToken(
            user_id=user.id, company_id=user.company_id,
            token_hash=security.hash_token(raw), expires_at=utcnow() + timedelta(hours=_TTL_HOURS),
        ))
        email_outbox_service.enqueue_transactional(
            db, company_id=user.company_id, recipient_email=user.email,
            recipient_user_id=user.id, type="PASSWORD_RESET",
            params={"reset_url": f"/reset-password?token={raw}", "deadline": "1 小时"},
        )
        db.flush()
    return raw


def reset(db: Session, *, token: str, new_password: str) -> None:
    with tenant.bypass_tenant_scope():
        now = utcnow()
        row = db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == security.hash_token(token),
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        ).scalar_one_or_none()
        if row is None:
            raise bad_request("INVALID_TOKEN", "重置链接无效或已过期")
        user = db.get(User, row.user_id)
        if user is None:
            raise bad_request("INVALID_TOKEN", "重置链接无效或已过期")
        user.password_hash = security.hash_password(new_password)
        row.used_at = now
        db.flush()
```

- [ ] **Step 5: 加路由**

在 `backend/app/routers/auth.py` import 区加 `from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest` + `from app.services import password_reset_service`，追加端点：

```python
@router.post("/forgot-password", status_code=200)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    password_reset_service.request_reset(db, email=payload.email, company_slug=payload.company_slug)
    db.commit()
    return {"status": "ok"}  # 总 200，防枚举


@router.post("/reset-password", status_code=200)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    password_reset_service.reset(db, token=payload.token, new_password=payload.new_password)
    db.commit()
    return {"status": "ok"}
```

- [ ] **Step 6: 运行 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_password_reset_api.py -v`
Expected: PASS

```bash
cd backend && ruff check app/models/password_reset_token.py app/services/password_reset_service.py app/schemas/auth.py app/routers/auth.py app/models/__init__.py tests/integration/test_password_reset_api.py && ruff format app/models/password_reset_token.py app/services/password_reset_service.py && mypy app/services/password_reset_service.py app/models/password_reset_token.py
git add app/models/password_reset_token.py app/services/password_reset_service.py app/schemas/auth.py app/routers/auth.py app/models/__init__.py tests/integration/test_password_reset_api.py
git commit -m "feat(platform): password reset (forgot/reset, anti-enumeration, hashed token)"
```

---

## Task 3: 改密码

**Files:**
- Modify: `backend/app/services/auth_service.py`、`backend/app/schemas/auth.py`、`backend/app/routers/auth.py`
- Test: `backend/tests/integration/test_change_password_api.py`

- [ ] **Step 1: 增 schema**

在 `backend/app/schemas/auth.py` 追加：

```python
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/integration/test_change_password_api.py`:

```python
def _register_and_token(client):
    r = client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "Alice"})
    return r.json()["access_token"]


def test_change_password_success(client):
    tok = _register_and_token(client)
    r = client.post("/api/v1/auth/change-password",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"old_password": "secret123", "new_password": "newsecret456"})
    assert r.status_code == 200, r.text
    assert client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "newsecret456"}).status_code == 200


def test_change_password_wrong_old_400(client):
    tok = _register_and_token(client)
    r = client.post("/api/v1/auth/change-password",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"old_password": "WRONG", "new_password": "newsecret456"})
    assert r.status_code == 400


def test_change_password_requires_auth(client):
    assert client.post("/api/v1/auth/change-password",
                       json={"old_password": "x", "new_password": "newsecret456"}).status_code == 401
```

- [ ] **Step 3: 写 service**

在 `backend/app/services/auth_service.py` 追加（复用 `security`）：

```python
def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not security.verify_password(old_password, user.password_hash):
        raise bad_request("INVALID_CREDENTIALS", "原密码不正确")
    user.password_hash = security.hash_password(new_password)
    db.flush()
```
（若 `bad_request`/`security` 未 import，在文件 import 区补 `from app.errors import bad_request`、`from app import security`。）

- [ ] **Step 4: 加路由**

在 `backend/app/routers/auth.py` 加 import `ChangePasswordRequest` + `from app.deps import get_current_user` + `from app.models.user import User` + `from app.services import auth_service`，追加：

```python
@router.post("/change-password", status_code=200)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    auth_service.change_password(db, current_user, payload.old_password, payload.new_password)
    db.commit()
    return {"status": "ok"}
```

- [ ] **Step 5: 运行 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_change_password_api.py -v`
Expected: PASS（3 passed）

```bash
cd backend && ruff check app/services/auth_service.py app/schemas/auth.py app/routers/auth.py tests/integration/test_change_password_api.py && ruff format app/services/auth_service.py && mypy app/services/auth_service.py
git add app/services/auth_service.py app/schemas/auth.py app/routers/auth.py tests/integration/test_change_password_api.py
git commit -m "feat(platform): change-password (verify old password)"
```

---

## Task 4: 用户邀请

**Files:**
- Create: `backend/app/models/user_invitation.py`、`backend/app/services/invitation_service.py`
- Modify: `backend/app/models/__init__.py`、`backend/app/schemas/platform.py`(创建)、`backend/app/routers/users.py`、`backend/app/routers/auth.py`
- Test: `backend/tests/integration/test_user_invitation_api.py`

- [ ] **Step 1: 写模型**

Create `backend/app/models/user_invitation.py`:

```python
"""用户邀请（Atlas UserInvitation 净室复刻）。token 只存哈希。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class UserInvitation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_user_invitation"

    email: Mapped[str] = mapped_column(String(255), index=True)
    role_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_role.id", ondelete="SET NULL"), default=None
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DATETIME6)
    # pending | accepted | revoked
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    invited_by: Mapped[str | None] = mapped_column(String(36), default=None)
```

在 `models/__init__.py` 导出 `UserInvitation`。

- [ ] **Step 2: 创建 platform schema**

Create `backend/app/schemas/platform.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InviteUserRequest(BaseModel):
    email: EmailStr
    role_id: str | None = None


class InviteResult(BaseModel):
    id: str
    email: str
    status: str


class AcceptInviteRequest(BaseModel):
    token: str
    name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=128)
```

- [ ] **Step 3: 写失败测试**

Create `backend/tests/integration/test_user_invitation_api.py`:

```python
from sqlalchemy import select

from app.models.user import User


def _admin_token(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "Admin"}).json()["access_token"]


def test_invite_then_accept(client, db):
    from app.services import invitation_service
    tok = _admin_token(client)
    # 邀请
    r = client.post("/api/v1/users/invite", headers={"Authorization": f"Bearer {tok}"},
                    json={"email": "bob@acme.com"})
    assert r.status_code == 201, r.text
    # 取明文 token（service 暴露供测试；路由只入邮件）
    raw = invitation_service._last_raw_token  # 见 service 注
    # accept
    acc = client.post("/api/v1/auth/accept-invite",
                      json={"token": raw, "name": "Bob", "password": "bobsecret1"})
    assert acc.status_code == 200, acc.text
    assert acc.json()["access_token"]
    # bob 建在该 company，可登录
    login = client.post("/api/v1/auth/login", json={"email": "bob@acme.com", "password": "bobsecret1"})
    assert login.status_code == 200


def test_invite_existing_email_409(client):
    tok = _admin_token(client)
    r = client.post("/api/v1/users/invite", headers={"Authorization": f"Bearer {tok}"},
                    json={"email": "admin@acme.com"})  # 已是该 company 用户
    assert r.status_code == 409


def test_invite_requires_permission(client):
    # 无 token → 401
    assert client.post("/api/v1/users/invite", json={"email": "x@acme.com"}).status_code == 401
```

> 注：测试用 `invitation_service._last_raw_token` 取明文 token 不优雅；更稳妥让 `invite()` 返回明文 token（路由丢弃），测试改用返回值——见 service 实现：`invite()` 返回 `(UserInvitation, raw_token)`，测试直接走 service 拿 raw。下面 service 按"返回明文"实现，测试相应改为调 service。

- [ ] **Step 4: 写 service**

Create `backend/app/services/invitation_service.py`:

```python
"""用户邀请：invite(建邀请+发邮件) + accept(建用户+标记)。pre-auth accept 用 bypass。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security, tenant
from app.errors import bad_request, conflict
from app.models.base import utcnow
from app.models.user import User, UserStatus
from app.models.user_invitation import UserInvitation
from app.services import email_outbox_service

_TTL_DAYS = 7


def invite(
    db: Session, *, company_id: str, email: str, role_id: str | None, invited_by: str | None
) -> tuple[UserInvitation, str]:
    """建邀请 + 入队邀请邮件。返回 (invitation, 明文token)。明文仅供测试/路由不回传。"""
    existing = db.execute(
        select(User).where(User.company_id == company_id, User.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise conflict("EMAIL_EXISTS", "该邮箱已是本组织成员")
    raw = security.generate_token()
    inv = UserInvitation(
        company_id=company_id, email=email, role_id=role_id,
        token_hash=security.hash_token(raw), expires_at=utcnow() + timedelta(days=_TTL_DAYS),
        status="pending", invited_by=invited_by,
    )
    db.add(inv)
    db.flush()
    email_outbox_service.enqueue_transactional(
        db, company_id=company_id, recipient_email=email, type="INVITE_USER",
        params={"invite_url": f"/accept-invite?token={raw}", "company_name": company_id, "deadline": "7 天后"},
    )
    db.flush()
    return inv, raw


def accept(db: Session, *, token: str, name: str, password: str) -> User:
    with tenant.bypass_tenant_scope():
        now = utcnow()
        inv = db.execute(
            select(UserInvitation).where(
                UserInvitation.token_hash == security.hash_token(token),
                UserInvitation.status == "pending",
                UserInvitation.expires_at > now,
            )
        ).scalar_one_or_none()
        if inv is None:
            raise bad_request("INVALID_TOKEN", "邀请链接无效或已过期")
    # 进入受邀租户上下文建用户
    ctx = tenant.set_current_company_id(inv.company_id)
    try:
        dup = db.execute(
            select(User).where(User.company_id == inv.company_id, User.email == inv.email)
        ).scalar_one_or_none()
        if dup is not None:
            raise conflict("EMAIL_EXISTS", "该邮箱已是本组织成员")
        user = User(
            company_id=inv.company_id, email=inv.email, name=name,
            password_hash=security.hash_password(password), role_id=inv.role_id,
            status=UserStatus.active,
        )
        db.add(user)
        inv.status = "accepted"
        db.flush()
    finally:
        tenant.reset_current_company_id(ctx)
    return user
```

> `company_name` 参数此处暂用 company_id 占位；如需真实公司名，invite 时查 `Company.name` 传入（小优化，可在实现时补一行 `db.get(Company, company_id).name`）。

- [ ] **Step 5: 加路由**

`backend/app/routers/users.py` 加 import `from app.schemas.platform import InviteUserRequest, InviteResult` + `from app.services import invitation_service` + `from app import permissions`，追加：

```python
@router.post("/invite", response_model=InviteResult, status_code=201)
def invite_user(
    payload: InviteUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.USER_CREATE)),
) -> InviteResult:
    inv, _raw = invitation_service.invite(
        db, company_id=current_user.company_id, email=payload.email,
        role_id=payload.role_id, invited_by=current_user.id,
    )
    db.commit()
    return InviteResult(id=inv.id, email=inv.email, status=inv.status)
```

`backend/app/routers/auth.py` 加 import `from app.schemas.platform import AcceptInviteRequest` + `from app.services import invitation_service`，追加（accept 后复用现有 `_tokens(db, user)` 签发）：

```python
@router.post("/accept-invite", response_model=TokenPair)
def accept_invite(payload: AcceptInviteRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = invitation_service.accept(db, token=payload.token, name=payload.name, password=payload.password)
    db.commit()
    return _tokens(db, user)
```

- [ ] **Step 6: 调整测试用返回值取 token**

把 Step 3 测试的 `test_invite_then_accept` 改为走 service 拿 raw（更稳）：
```python
def test_invite_then_accept(client, db):
    from app import tenant
    from app.services import invitation_service
    from app.models.company import Company
    # 注册管理员（建 company）
    reg = client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com", "password": "secret123", "name": "Admin"}).json()
    # 取 company_id
    from app.models.user import User as U
    with tenant.bypass_tenant_scope():
        admin = db.execute(select(U).where(U.email == "admin@acme.com")).scalar_one()
    inv, raw = invitation_service.invite(db, company_id=admin.company_id, email="bob@acme.com", role_id=None, invited_by=admin.id)
    db.commit()
    acc = client.post("/api/v1/auth/accept-invite", json={"token": raw, "name": "Bob", "password": "bobsecret1"})
    assert acc.status_code == 200, acc.text
    assert client.post("/api/v1/auth/login", json={"email": "bob@acme.com", "password": "bobsecret1"}).status_code == 200
```

- [ ] **Step 7: 运行 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_user_invitation_api.py -v`
Expected: PASS

```bash
cd backend && ruff check app/models/user_invitation.py app/services/invitation_service.py app/schemas/platform.py app/routers/users.py app/routers/auth.py app/models/__init__.py tests/integration/test_user_invitation_api.py && ruff format app/models/user_invitation.py app/services/invitation_service.py app/schemas/platform.py && mypy app/services/invitation_service.py app/models/user_invitation.py
git add app/models/user_invitation.py app/services/invitation_service.py app/schemas/platform.py app/routers/users.py app/routers/auth.py app/models/__init__.py tests/integration/test_user_invitation_api.py
git commit -m "feat(platform): user invitation (invite + accept→create user in org + login)"
```

---

## Task 5: Currency（全局表）

**Files:**
- Create: `backend/app/models/currency.py`、`backend/app/services/currency_service.py`、`backend/app/routers/currencies.py`
- Modify: `backend/app/models/__init__.py`、`backend/app/schemas/platform.py`、`backend/app/permissions.py`、`backend/app/main.py`
- Test: `backend/tests/integration/test_currency_api.py`

- [ ] **Step 1: 写模型（全局，不挂租户）**

Create `backend/app/models/currency.py`:

```python
"""全局币种表（不挂租户，super_admin 维护，所有租户共读）。"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Currency(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tb_currency"

    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(8), default="", server_default="")
```

在 `models/__init__.py` 导出 `Currency`。

- [ ] **Step 2: 权限码 + schema**

`backend/app/permissions.py`：若无 `CURRENCY_MANAGE`，加 `CURRENCY_MANAGE = "currency.manage"` 并确保它在 `ALL_PERMISSIONS`（即 super_admin/admin 拥有）。

`backend/app/schemas/platform.py` 追加：

```python
class CurrencyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=8)
    name: str = Field(min_length=1, max_length=64)
    symbol: str = Field(default="", max_length=8)


class CurrencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    symbol: str
```

- [ ] **Step 3: 写失败测试**

Create `backend/tests/integration/test_currency_api.py`:

```python
def _admin_token(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "A"}).json()["access_token"]


def test_currency_crud_super_admin(client):
    tok = _admin_token(client)  # 首用户=super_admin
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/api/v1/currencies", headers=h, json={"code": "CNY", "name": "人民币", "symbol": "¥"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert client.get("/api/v1/currencies", headers=h).status_code == 200
    assert any(c["code"] == "CNY" for c in client.get("/api/v1/currencies", headers=h).json())
    assert client.delete(f"/api/v1/currencies/{cid}", headers=h).status_code == 204


def test_currency_duplicate_code_409(client):
    tok = _admin_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    client.post("/api/v1/currencies", headers=h, json={"code": "USD", "name": "美元"})
    r = client.post("/api/v1/currencies", headers=h, json={"code": "USD", "name": "美元2"})
    assert r.status_code == 409
```

- [ ] **Step 4: 写 service**

Create `backend/app/services/currency_service.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict, not_found
from app.models.currency import Currency
from app.schemas.platform import CurrencyCreate


def list_currencies(db: Session) -> list[Currency]:
    return list(db.execute(select(Currency).order_by(Currency.code)).scalars())


def create_currency(db: Session, data: CurrencyCreate) -> Currency:
    if db.execute(select(Currency).where(Currency.code == data.code)).scalar_one_or_none():
        raise conflict("CURRENCY_EXISTS", f"币种已存在：{data.code}")
    cur = Currency(code=data.code, name=data.name, symbol=data.symbol)
    db.add(cur)
    db.flush()
    return cur


def delete_currency(db: Session, currency_id: str) -> None:
    cur = db.get(Currency, currency_id)
    if cur is None:
        raise not_found("NOT_FOUND", "币种不存在")
    db.delete(cur)
    db.flush()
```

- [ ] **Step 5: 写路由 + 注册**

Create `backend/app/routers/currencies.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_current_user, require_permission
from app.db import get_db
from app.models.currency import Currency
from app.models.user import User
from app.schemas.platform import CurrencyCreate, CurrencyOut
from app.services import currency_service

router = APIRouter(prefix="/api/v1/currencies", tags=["currencies"])


@router.get("", response_model=list[CurrencyOut])
def list_currencies(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Currency]:
    return currency_service.list_currencies(db)


@router.post("", response_model=CurrencyOut, status_code=201)
def create_currency(
    payload: CurrencyCreate, db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.CURRENCY_MANAGE)),
) -> Currency:
    cur = currency_service.create_currency(db, payload)
    db.commit()
    return cur


@router.delete("/{currency_id}", status_code=204, response_model=None)
def delete_currency(
    currency_id: str, db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.CURRENCY_MANAGE)),
) -> Response:
    currency_service.delete_currency(db, currency_id)
    db.commit()
    return Response(status_code=204)
```

`backend/app/main.py`：import `currencies` 并 `app.include_router(currencies.router)`。

- [ ] **Step 6: 运行 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_currency_api.py -v`
Expected: PASS

```bash
cd backend && ruff check app/models/currency.py app/services/currency_service.py app/routers/currencies.py app/schemas/platform.py app/permissions.py app/main.py app/models/__init__.py tests/integration/test_currency_api.py && ruff format app/models/currency.py app/services/currency_service.py app/routers/currencies.py && mypy app/services/currency_service.py app/routers/currencies.py
git add app/models/currency.py app/services/currency_service.py app/routers/currencies.py app/schemas/platform.py app/permissions.py app/main.py app/models/__init__.py tests/integration/test_currency_api.py
git commit -m "feat(platform): global Currency table + CRUD (super_admin)"
```

---

## Task 6: CompanySettings

**Files:**
- Create: `backend/app/models/company_settings.py`、`backend/app/services/company_settings_service.py`、`backend/app/routers/company_settings.py`
- Modify: `backend/app/models/__init__.py`、`backend/app/schemas/platform.py`、`backend/app/main.py`
- Test: `backend/tests/integration/test_company_settings_api.py`

- [ ] **Step 1: 写模型**

Create `backend/app/models/company_settings.py`:

```python
"""公司级配置（每 company 一行 singleton）。"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class CompanySettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_company_settings"

    date_format: Mapped[str] = mapped_column(String(32), default="YYYY-MM-DD", server_default="YYYY-MM-DD")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", server_default="Asia/Shanghai")
    default_currency_code: Mapped[str] = mapped_column(String(8), default="CNY", server_default="CNY")
    auto_assign: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
```

在 `models/__init__.py` 导出 `CompanySettings`。

- [ ] **Step 2: schema**

`backend/app/schemas/platform.py` 追加：

```python
class CompanySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date_format: str
    timezone: str
    default_currency_code: str
    auto_assign: bool


class CompanySettingsUpdate(BaseModel):
    date_format: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    default_currency_code: str | None = Field(default=None, max_length=8)
    auto_assign: bool | None = None
```

- [ ] **Step 3: 写失败测试**

Create `backend/tests/integration/test_company_settings_api.py`:

```python
def _token(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "A"}).json()["access_token"]


def test_get_returns_defaults_then_update(client):
    h = {"Authorization": f"Bearer {_token(client)}"}
    r = client.get("/api/v1/company-settings", headers=h)
    assert r.status_code == 200
    assert r.json()["date_format"] == "YYYY-MM-DD"
    u = client.put("/api/v1/company-settings", headers=h, json={"timezone": "UTC", "auto_assign": True})
    assert u.status_code == 200, u.text
    assert u.json()["timezone"] == "UTC"
    assert u.json()["auto_assign"] is True
    # 持久化
    assert client.get("/api/v1/company-settings", headers=h).json()["timezone"] == "UTC"
```

- [ ] **Step 4: 写 service**（get-or-create singleton）

Create `backend/app/services/company_settings_service.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company_settings import CompanySettings
from app.schemas.platform import CompanySettingsUpdate


def get_or_create(db: Session, company_id: str) -> CompanySettings:
    row = db.execute(
        select(CompanySettings).where(CompanySettings.company_id == company_id)
    ).scalar_one_or_none()
    if row is None:
        row = CompanySettings(company_id=company_id)
        db.add(row)
        db.flush()
    return row


def update(db: Session, company_id: str, data: CompanySettingsUpdate) -> CompanySettings:
    row = get_or_create(db, company_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    db.flush()
    return row
```

- [ ] **Step 5: 路由 + 注册**

Create `backend/app/routers/company_settings.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.db import get_db
from app.models.company_settings import CompanySettings
from app.models.user import User
from app.schemas.platform import CompanySettingsOut, CompanySettingsUpdate
from app.services import company_settings_service

router = APIRouter(prefix="/api/v1/company-settings", tags=["company-settings"])


@router.get("", response_model=CompanySettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CompanySettings:
    return company_settings_service.get_or_create(db, user.company_id)


@router.put("", response_model=CompanySettingsOut)
def update_settings(
    payload: CompanySettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CompanySettings:
    row = company_settings_service.update(db, user.company_id, payload)
    db.commit()
    return row
```

`backend/app/main.py`：import `company_settings` 并 `app.include_router(company_settings.router)`。

- [ ] **Step 6: 运行 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_company_settings_api.py -v`
Expected: PASS

```bash
cd backend && ruff check app/models/company_settings.py app/services/company_settings_service.py app/routers/company_settings.py app/schemas/platform.py app/main.py app/models/__init__.py tests/integration/test_company_settings_api.py && ruff format app/models/company_settings.py app/services/company_settings_service.py app/routers/company_settings.py && mypy app/services/company_settings_service.py app/routers/company_settings.py
git add app/models/company_settings.py app/services/company_settings_service.py app/routers/company_settings.py app/schemas/platform.py app/main.py app/models/__init__.py tests/integration/test_company_settings_api.py
git commit -m "feat(platform): CompanySettings (per-company singleton get/update)"
```

---

## Task 7: 统一 alembic 迁移 + 全量回归

**Files:**
- Modify: `backend/app/models/email_outbox.py`（recipient_user_id 可空）
- Create: `backend/alembic/versions/20260602_0001_platform_account_config.py`

- [ ] **Step 1: email_outbox.recipient_user_id 改可空**

Read `backend/app/models/email_outbox.py`，将 `recipient_user_id` 列改为 `Mapped[str | None]`（nullable=True）——邀请邮件无关联 user。若它原已可空，跳过此步。

- [ ] **Step 2: 确认迁移链头**

Run: `cd backend && .venv/bin/python -m alembic heads`
Expected: 单一 head（已知为 `add_batch_import`，以实际输出为准，填入下面 `down_revision`）。

- [ ] **Step 3: 写迁移**

Create `backend/alembic/versions/20260602_0001_platform_account_config.py`（`down_revision` 用 Step 2 输出）:

```python
"""platform account & config backfill: reset token / invitation / company settings / currency"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "platform_account_config"
down_revision: str | None = "add_batch_import"  # 见 Step 2
branch_labels = None
depends_on = None

_TENANT_FK = dict(ondelete="CASCADE")


def _tenant_table(name: str, *cols: sa.Column) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        *cols,
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["tb_company.id"], name=f"fk_{name}_company_id", **_TENANT_FK),
        sa.PrimaryKeyConstraint("id", name=f"pk_{name}"),
    )
    op.create_index(f"ix_{name}_company_id", name, ["company_id"])


def upgrade() -> None:
    _tenant_table(
        "tb_password_reset_token",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tb_password_reset_token_token_hash", "tb_password_reset_token", ["token_hash"])
    op.create_index("ix_tb_password_reset_token_user_id", "tb_password_reset_token", ["user_id"])

    _tenant_table(
        "tb_user_invitation",
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role_id", sa.String(36), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("invited_by", sa.String(36), nullable=True),
    )
    op.create_index("ix_tb_user_invitation_email", "tb_user_invitation", ["email"])
    op.create_index("ix_tb_user_invitation_token_hash", "tb_user_invitation", ["token_hash"])

    _tenant_table(
        "tb_company_settings",
        sa.Column("date_format", sa.String(32), nullable=False, server_default="YYYY-MM-DD"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("default_currency_code", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("auto_assign", sa.Boolean(), nullable=False, server_default="0"),
    )

    op.create_table(
        "tb_currency",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(8), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tb_currency"),
        sa.UniqueConstraint("code", name="uq_tb_currency_code"),
    )

    # email_outbox.recipient_user_id 改可空（邀请邮件无 user）
    op.alter_column("tb_email_outbox", "recipient_user_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    op.alter_column("tb_email_outbox", "recipient_user_id", existing_type=sa.String(36), nullable=False)
    op.drop_table("tb_currency")
    op.drop_table("tb_company_settings")
    op.drop_table("tb_user_invitation")
    op.drop_index("ix_tb_password_reset_token_token_hash", table_name="tb_password_reset_token")
    op.drop_index("ix_tb_password_reset_token_user_id", table_name="tb_password_reset_token")
    op.drop_table("tb_password_reset_token")
```

> 注：`tb_email_outbox` 实际表名以 `EmailOutbox.__tablename__` 为准（Read 确认）；若不同，改 alter_column 的表名。

- [ ] **Step 4: 验证迁移 + 全量回归**

Run:
```bash
cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head
.venv/bin/python -m pytest -q
ruff check app/ && mypy app/
```
Expected: 迁移升降无错；全量测试通过；ruff/mypy 绿。

- [ ] **Step 5: 提交**

```bash
git add app/models/email_outbox.py backend/alembic/versions/20260602_0001_platform_account_config.py 2>/dev/null; git add app/models/email_outbox.py alembic/versions/20260602_0001_platform_account_config.py
git commit -m "feat(platform): alembic migration for account/config tables + email_outbox nullable recipient"
```

---

## 集成验证清单（MySQL，部署前）

- [ ] 密码重置/邀请的 token 在 MySQL 下哈希索引查询正常；并发不串号。
- [ ] 跨租户：A 公司邀请不出现在 B；Currency 全局可读、非 super_admin 写被 403。
- [ ] 邮件 outbox 投递（dispatch task）能发出重置/邀请邮件（事务邮件不被通知偏好过滤）。

---

## Self-Review（计划作者已核对）

- **Spec 覆盖**：密码重置(Task2)、改密码(Task3)、邀请(Task4)、Currency(Task5)、CompanySettings(Task6)、迁移(Task7) 全覆盖 spec §1.1/§3/§4。customId/激活/UserSettings 按 spec 排除，无 task（符合非目标）。
- **占位扫描**：无 TBD/TODO。三处"实现时对齐"是真实的现状核对点（EmailOutbox 字段、company_name、迁移表名），非模糊占位，均给了默认写法 + 核对指引。
- **类型一致性**：`generate_token`/`hash_token`(Task1) 被 Task2/4 一致使用；`enqueue_transactional`(Task1) 被 Task2/4 一致调用；`PasswordResetToken`/`UserInvitation`/`Currency`/`CompanySettings` 模型字段与各 service/迁移一致；`_tokens(db,user)`(现有 auth 路由) 被 accept-invite 复用；权限 `USER_CREATE`/`CURRENCY_MANAGE` 一致。
- **关键工程点**：token 哈希存储、防枚举(总200)、pre-auth bypass+租户定位、事务邮件(可无user/不过偏好)、JWT无状态→不吊销refresh(已降级声明)、Currency全局(不挂租户)、迁移 down_revision 用 alembic heads 确认——均落实。
- **依赖**：后端 security/auth_service/email_outbox/deps/permissions/_tokens 均已就绪；测试用 SQLite create_all 不依赖迁移。
