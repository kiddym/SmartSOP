# 平台账户与配置补全 — 设计文档（Atlas 复刻补全 · 第 1 组之 ①）

- 日期：2026-06-02
- 状态：设计草案，待评审（实施计划另立 / writing-plans）
- 背景：核实发现"已完成模块未完全复刻 Atlas"（见 `atlas-parity-backfill`）。本 spec 补齐**平台账户与配置层**的 Atlas 功能缺口。属"先补全再做下一阶段"决策下的第一组补全之 ①（②为通用附件基础设施，另立）。
- 关联：[Atlas 复刻 gap 总账](../specs/2026-06-01-remaining-work-audit.md) · 净室红线见 `cmms-clean-room-baseline`（记忆）

---

## 1. 目标与范围

补齐平台层相对 Atlas 的账户生命周期与配置缺口，让平台模块真正完整可用（认证地基已完成，本组是其后端配套）。

### 1.1 范围（后端，净室——参照 Atlas 行为全新原创）
- **用户生命周期**：密码重置（token + 邮件）、用户邀请（UserInvitation + 邮件 + 接受加入已有组织）、改密码（校验旧密码）。
- **配置**：CompanySettings（每公司配置：日期格式/时区/默认币种/自动指派等开关）、Currency（全局币种表，super_admin 维护）。

### 1.2 明确不做（范围决策）
- **customId 通用化**：✅ **已实现**——`sequence_service.next_value(db, scope, company_id)` per (company_id, scope) 原子自增 + `format_custom_id`，asset/work_order/request/po/pm/meter/part/multi_part 均已用。**无 gap，不在本 spec。**
- **邮箱激活**：本轮不做强制（现注册即 active、首用户=super_admin，认证已上线；激活归"后期"项）。
- **UserSettings（邮件通知开关）**：移到"通知完善"阶段（与通知系统耦合）。
- **SSO/OAuth、多组织切换**：后期项，不在本轮。

---

## 2. 组件分解

复用：`email_outbox`（重置/邀请邮件入队 + 现有 dispatch task）、`auth_service`/`security`（密码哈希、token）、`User`/`Role` 模型、`tenant` 的 bypass + pre-auth 租户定位（同 login/register）、`require_permission`。

| 文件 | 类型 | 职责 |
|---|---|---|
| `models/password_reset_token.py` | 新增 | PasswordResetToken（token 哈希/过期/单次） |
| `models/user_invitation.py` | 新增 | UserInvitation（email/role/token/status/invited_by） |
| `models/company_settings.py` | 新增 | CompanySettings（每公司一行配置） |
| `models/currency.py` | 新增 | Currency（全局币种表） |
| `services/password_reset_service.py` | 新增 | forgot/reset 流 + token 生成校验 |
| `services/invitation_service.py` | 新增 | invite/accept 流 |
| `services/auth_service.py` | 改 | 增 change_password（校验旧密码） |
| `services/company_settings_service.py` | 新增 | get/update（singleton per company） |
| `services/currency_service.py` | 新增 | CRUD（super_admin） |
| `routers/auth.py` | 改 | 增 forgot-password / reset-password / change-password / accept-invite |
| `routers/users.py` | 改 | 增 invite（+ 可选 列待处理/撤销） |
| `routers/company_settings.py` | 新增 | GET/PUT /company-settings |
| `routers/currencies.py` | 新增 | Currency CRUD |
| `email/templates.py` | 改 | 增 密码重置 / 邀请 中文模板 |
| alembic 迁移 | 新增 | 4 张新表 |

---

## 3. 数据流

**① 密码重置**（token + 邮件，pre-auth）
```
POST /auth/forgot-password {email, company_slug?}
  → bypass 查租户内用户(复用 login 的 pre-auth 租户定位) → 生成 PasswordResetToken
    (随机明文 token 仅入邮件；DB 存其哈希；expires≈1h；单次)
  → email outbox 发重置邮件(含 token) → 无论用户是否存在均返 200(防枚举)
POST /auth/reset-password {token, new_password}
  → 校验 token(存在/未过期/未用) → 更新密码哈希 → 标 used → 吊销该用户现有 refresh
```

**② 用户邀请**（UserInvitation + 邮件 + 接受）
```
POST /users/invite {email, role_id}   (require_permission user.create，管理员租户上下文)
  → 建 UserInvitation(email, company_id, role_id, token哈希, expires, status=pending, invited_by)
  → email outbox 发邀请邮件(含 token)
POST /auth/accept-invite {token, name, password}   (pre-auth)
  → 校验 token(pending/未过期) → bypass+set 该 company 上下文 → 在该 company 建 User
    (email 租户内唯一约束复用，绑 invitation.role) → 标 accepted → 签发 TokenPair(直接登录)
```
可选：`GET /users/invitations`(列 pending)、`POST /users/invitations/{id}/revoke`。

**③ 改密码**（authed）
```
POST /auth/change-password {old_password, new_password}  (get_current_user)
  → 校验旧密码 → 更新哈希
```

**④ 配置**
- **CompanySettings**：每 company 一行(singleton)，`GET/PUT /company-settings`（无则返默认）。
- **Currency**：全局表，`GET /currencies`(任意已认证可读)、`POST/PATCH/DELETE /currencies`(super_admin)；CompanySettings.default_currency_code 引用。

**贯穿安全/租户**：token 一律存哈希不存明文、单次+过期；forgot 防枚举(总 200)；邀请 email 租户内唯一；pre-auth 流复用现有 login/register 的 bypass+租户定位。

---

## 4. 模型字段

| 模型 | 关键字段 | 租户 |
|---|---|---|
| `PasswordResetToken` | user_id(FK)、company_id、`token_hash`(String64)、expires_at、used_at(nullable) | TenantMixin |
| `UserInvitation` | company_id、email、role_id(FK)、`token_hash`、expires_at、status(pending/accepted/revoked/expired)、invited_by(FK) | TenantMixin |
| `CompanySettings` | company_id(unique)、date_format、timezone、default_currency_code、auto_assign(bool)… | TenantMixin，每 company 一行 |
| `Currency` | code(unique 如 CNY/USD)、name、symbol | **全局表（不挂租户 mixin）**——平台级共享、super_admin 维护 |

> ⚠️ `Currency` 是**全局**的（不挂 TenantScoped、所有租户共读、super_admin 维护），有意区别于其余平台表（都挂 TenantMixin）。

---

## 5. 错误处理

| 场景 | 处理 |
|---|---|
| forgot-password（用户存在与否） | 总返 200（防枚举） |
| reset/accept-invite token 无效/过期/已用 | 400 / 410 |
| 邀请 email 已是该 company 用户 | 409 |
| 改密旧密码错 / 密码<8 位 | 400 |
| Currency code 重复 | 409 |
| invite/currency 权限不足 | 403（require_permission） |

---

## 6. 测试策略（pytest + SQLite，对齐项目门禁 ruff 0.15/mypy 1.20）

- 密码重置全流（生成→reset→旧 token 失效 + refresh 吊销）；**防枚举**（不存在 email 也 200）。
- 邀请全流（invite→accept→user 建于**正确 company 带 role**）；**跨租户对抗**（A 邀请不泄漏到 B）；email 租户内唯一；token 单次/过期。
- 改密码（旧密码错拒）。
- CompanySettings get/update（singleton）。
- Currency CRUD + super_admin 权限校验（非 super_admin 写 → 403）。

---

## 7. 迁移与净室

- **迁移**：alembic 新增 4 表（PasswordResetToken/UserInvitation/CompanySettings/Currency）；`down_revision` 指向认证合并后的 main 链头，写 plan 时用 `alembic heads` 确认。
- **邮件**：复用现有 email outbox + 新增密码重置/邀请**中文**模板（仅中文，不做 i18n）。
- **净室声明**：参照 Atlas 的 VerificationToken/UserInvitation/CompanySettings/Currency 的**功能行为**全新原创实现；不复制其源码、字段命名、文案、DDL。

---

## 8. 实现顺序建议（细化留给 writing-plans）

1. 密码重置（PasswordResetToken + service + auth 路由 + 邮件模板）
2. 改密码（auth_service.change_password + 路由）
3. 用户邀请（UserInvitation + invitation_service + users/auth 路由 + 邮件模板）
4. Currency（全局表 + service + 路由 + super_admin 权限）
5. CompanySettings（依赖 Currency 的 default_currency_code）

依赖：⑤ 依赖 ④（默认币种引用）；其余相对独立。
