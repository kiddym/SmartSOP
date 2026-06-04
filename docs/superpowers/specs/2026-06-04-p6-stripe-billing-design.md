# P6 Stripe 计费 MVP 设计

> Phase 6 商业化的支付落地轮次。P6 门控骨架已成型（`Company.plan`/`subscription_status` 为真相源，catalog + `require_feature` 门控 + `GET /billing/subscription` 自查 + 平台 admin 手动设档 + 前端 PlansView），但 plan/status 此前仅能手动设置。本轮接入 **Stripe（test-mode）** 让 **pro 档由真实支付驱动**：托管 Checkout 订阅 → webhook 同步 → 客户门户管理 → 取消降级。

## 范围与已确认决策

- **交付深度 = MVP 订阅闭环**：pro 自助订阅（托管 Checkout）→ webhook 同步 `plan`/`subscription_status` → 取消/重订 → 客户门户改支付。覆盖核心生命周期 `active` / `past_due` / `canceled`。
- **定价 = 按档包月**：单一 Stripe Price（pro 月费）。座位上限沿用现有邀请门控（free=3 / pro=15 / enterprise=∞），不按座计量。
- **机制 = 托管 Checkout + Customer Portal**：卡号不经我们后端（PCI 负担最低）。
- **enterprise = 联系销售**：不走 Stripe 自助，复用现有平台 admin 手动设档端点授档。free 无 Stripe。
- **真相源 = Stripe webhook**：`customer.subscription.*` 事件驱动 `Company` 字段。
- **本轮 = test-mode**：Stripe 测试密钥 + Stripe CLI 转发 webhook；上线（live）非本轮目标。

## 净室红线

Stripe 官方 SDK / 文档为公共标准接口，正常使用即可；绝不复制任何第三方（尤其 Atlas）的计费代码 / DDL / 命名 / 文案；产品中不出现 "Atlas"。见 [[cmms-clean-room-baseline]]。

## 组件与改动

### 1. 数据模型

`Company` 加两列（均 String nullable，不涉 TEXT 字面默认 1101，见 [[mysql-text-default-blocks-bootstrap]]）：
- `stripe_customer_id: str | None`（unique）——一个公司一个 Stripe Customer。
- `stripe_subscription_id: str | None`——当前活跃订阅 id（便于门户/排障）。

新表 `tb_billing_event`（webhook 去重日志，防 Stripe 重发重复处理）：
- `event_id: str`（Stripe event id，主键）
- `event_type: str`
- `processed_at: datetime`
- 非租户表（Stripe 事件按 customer 解析公司，事件本身不属单租户）。

`plan` / `subscription_status` 既有列不改。一个 alembic 迁移（加两列 + 建一表），`down_revision` 接当前单 head，迁移后仍单 head。

### 2. Stripe 网关（`app/billing/stripe_gateway.py`）

薄封装官方 `stripe` SDK，隔离外部依赖、便于单测 mock。纯函数式接口（接收/返回基本类型与 dict，不向上泄漏 SDK 对象）：
- `ensure_customer(*, company_id, email, existing_id) -> customer_id`：建或复用 Customer，metadata 带 `company_id`。
- `create_checkout_session(*, customer_id, price_id, success_url, cancel_url) -> url`：`mode=subscription`。
- `create_portal_session(*, customer_id, return_url) -> url`。
- `construct_event(payload: bytes, sig_header: str) -> dict`：验签并解析事件（失败抛）。
- `retrieve_subscription(subscription_id) -> dict`（webhook 补取所需字段时用）。

SDK key 从 `settings.stripe_secret_key` 注入（模块级配置一次）。

### 3. 计费服务（`app/services/billing_service.py`）

业务编排，不直接碰 SDK（经 gateway）：
- `start_checkout(db, company, user) -> url`：`ensure_customer` 并把 `stripe_customer_id` 回写 `Company`（**checkout 前即落 customer id，确保 webhook 必能按 customer 反查公司**）→ `create_checkout_session`（price=pro）→ 返回 URL。
- `open_portal(db, company) -> url`：无 `stripe_customer_id` → 400（未订阅过）；否则 `create_portal_session`。
- `handle_event(db, payload, sig_header) -> None`：`construct_event` 验签 → 去重（`tb_billing_event` 命中即跳过）→ 按事件类型 `sync_from_subscription`。

**Webhook 同步逻辑（真相源）**——处理 `customer.subscription.created` / `updated` / `deleted`：
1. 按 `subscription.customer` 查 `Company.stripe_customer_id`；查无 → 记日志容错跳过（不抛，避免 Stripe 反复重投）。
2. `status` 映射 → `subscription_status`：
   - `active` / `trialing` → `active`
   - `past_due` / `unpaid` → `past_due`
   - `canceled` / `incomplete_expired` / 事件为 `deleted` → `canceled`
3. `plan` 映射：活跃订阅（price=pro）→ `pro`；取消/删除 → 回 `free`。
4. 活跃订阅记 `stripe_subscription_id`；取消/删除时清空（plan→free 已是权威降级）。
5. 写 `tb_billing_event(event_id)` 标记已处理。写 `Company` plan/status 本就幂等。

`checkout.session.completed` **不单独处理**（customer 已在 `start_checkout` 落库；订阅状态由 `customer.subscription.*` 权威同步）。

### 4. 路由（`app/routers/billing.py` 扩展）

- `POST /api/v1/billing/checkout-session`（权限 `billing.manage`）→ `{ url }`。
- `POST /api/v1/billing/portal-session`（`billing.manage`）→ `{ url }`。
- `POST /api/v1/billing/webhook`（**无认证**，读 `await request.body()` 原始字节 + `Stripe-Signature` 头验签）→ 验签失败 400；成功 200。
- `GET /api/v1/billing/subscription`（既有，不改）——前端 checkout 返回后轮询用。

### 5. 配置（`app/config.py`，pydantic-settings）

新增字段（密钥仅入 `.env`，仓库不存）：
- `stripe_secret_key: str = ""`
- `stripe_webhook_secret: str = ""`
- `stripe_price_pro: str = ""`（pro 月费 Price id）
- `billing_checkout_success_url` / `billing_checkout_cancel_url` / `billing_portal_return_url`（显式三个前端回跳 URL，指向 billing 页）
- `sales_contact_email: str = ""`（enterprise「联系销售」mailto；空则前端降级为纯文案）

### 6. 权限（`app/permissions.py`）

加 `BILLING_MANAGE = "billing.manage"`，并入 `ALL_PERMISSIONS`；内置 `admin` / `super_admin` 默认含（super_admin 已是通配）。门控 checkout/portal 端点。

### 7. 与平台手动设档共存

保留 `PATCH /api/v1/platform/companies/{id}/subscription`（平台 admin），用于 enterprise 授档 / 客服补偿 / 非 Stripe 公司。约定：**Stripe 自助订阅公司由 webhook 维护**；对其手动改档会被下次 webhook 覆盖（预期行为，文档注明）。两者写同一组 `plan`/`subscription_status` 字段。

### 8. 前端

- `PlansView.vue`：pro 卡片「订阅」按钮 → `POST /billing/checkout-session` → `window.location` 跳转；enterprise 卡片「联系销售」（`sales_contact_email` 有值→mailto，否则纯文案）；free 无按钮。已订阅 pro → 显示「管理订阅 / 改支付方式」→ `POST /billing/portal-session` → 跳转 Portal。
- Checkout success/cancel 返回 billing 页：因 webhook 异步，返回后**轮询 `GET /billing/subscription`** 直到 `plan` 翻新（显示「处理中…」，带次数上限/退避，超时提示稍后刷新）。
- `store/billing.ts`：加 `startCheckout` / `openPortal` action；复用既有 `hasFeature` / 订阅状态。

## 测试策略

- **后端单测（SQLite + mock `stripe_gateway`，纯应用逻辑）**：
  - webhook `handle_event`：subscription created/updated/deleted → `Company` plan/status 正确同步；幂等重放（同 event_id）不二次处理；未知 customer 容错跳过；`past_due`/`canceled` 映射。
  - 验签失败 → 400。
  - checkout / portal 端点（mock gateway 返回 URL）；`billing.manage` 门控（无权 403）；portal 未订阅 → 400。
- **迁移**：SQLite 往返绿 + 单 head；新列均 String，MySQL bootstrap 已通、env-gated `test_mysql_bootstrap` 自动覆盖新迁移链。
- **端到端手验（test-mode）**：`stripe listen --forward-to localhost:8000/api/v1/billing/webhook` + 测试卡走 checkout → 确认升 pro（功能解锁）→ portal 取消 → 确认降 free（门控回收）。dev 环境见 [[running-smartsop-dev]]。
- 不对真实 Stripe 做自动化（test-mode 手验 + mock 单测）。

## 边界与非目标

- 不做：免费试用、按座计量、proration 升降档、dunning 催收邮件、发票/收据 UI、年付。
- 不做：live 上线（仅 test-mode；上线 = 换 live keys + 建 live price + 配 prod webhook endpoint + 域名可达）。
- enterprise 自助、free 计费均不做。

## 前置依赖（操作项，非本设计交付）

实现期需你在 `.env` 填入（仓库不入密钥）：Stripe **test** secret key、pro 月费 Price id、webhook signing secret。实现计划会列清单与获取步骤。

## 验收标准

- pro 自助订阅闭环在 test-mode 跑通：checkout → webhook 升 `plan=pro`/`status=active` → 功能门控解锁；portal 取消 → webhook 降 `plan=free`/`status=canceled` → 门控回收。
- webhook 验签 + 幂等（重放不二次处理）+ 未知 customer 容错，均有单测覆盖。
- 后端 SQLite 全量绿、ruff/format/mypy 净、alembic 单 head 不变、迁移往返绿；前端 typecheck/lint/测试绿。
- 平台 admin 手动设档端点保留可用（enterprise 授档路径不破）。
- 净室红线不破；密钥不入仓库。
