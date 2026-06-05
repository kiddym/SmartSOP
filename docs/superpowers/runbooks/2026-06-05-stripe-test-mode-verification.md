# Stripe 真链路手验 Runbook（test-mode）

> **为什么需要你**：真链路手验必须有一个真实的 Stripe 账户（test-mode 也是绑定账户的私密凭证）。仓库不存密钥（`.env.example` 里是占位 `sk_test_...`），AI/CI 无法注册账户或获取密钥。逻辑层已被 **20 个测试**覆盖（`test_stripe_gateway` / `test_billing_subscription_api` / `test_billing_catalog` / `test_billing_config_perms` / `integration/test_billing_stripe_api` + 2 个迁移测试），所以这份手验只验「与真实 Stripe 的网络往返」这一层。拿到密钥后照做约 5–10 分钟走完。

## 已实现的契约（你验的就是它）

- 后端 `prefix=/api/v1/billing`：
  - `GET /subscription` → 当前订阅（plan/status）
  - `POST /checkout-session` → `{ url }`（托管 Checkout，需 `billing.manage`）
  - `POST /portal-session` → `{ url }`（托管 Customer Portal）
  - `POST /webhook` → Stripe 事件入口（验签 + 真相源同步 plan/status）
- 配置项（`backend/app/config.py`，经 `.env` 注入，仓库不存真值）：
  - `STRIPE_SECRET_KEY`、`STRIPE_WEBHOOK_SECRET`、`STRIPE_PRICE_PRO`
- 真相源模型：webhook 是唯一权威 —— `checkout.session.completed` / `customer.subscription.updated` / `.deleted` 同步公司的 plan/status；门控随 `active→pro 解锁`、`canceled/past_due→回锁`。enterprise 手动设档不受 webhook 影响。

---

## 一、准备 Stripe test-mode 资源（在 Stripe Dashboard，约 3 分钟）

1. 登录 <https://dashboard.stripe.com>，**右上角切到 Test mode**（务必，别用 live）。
2. **拿 Secret key**：Developers → API keys → 复制 `sk_test_...`（Secret key）。
3. **建 Pro 产品与价格**：Products → Add product → 名称如「Smart CMMS Pro」→ 加一个 **Recurring** 价格（如 ¥/月）→ 保存 → 复制该价格的 **Price ID**（`price_...`）。
4. **Webhook 签名密钥**有两种取法（二选一）：
   - **本地开发推荐用 Stripe CLI**（见第二步），它会临时打印一个 `whsec_...`。
   - 或 Dashboard → Developers → Webhooks → 加 endpoint 指向你的公网地址 `…/api/v1/billing/webhook`，复制其 `whsec_...`（仅当后端有公网可达地址时）。

## 二、配置并启动（约 2 分钟）

1. 编辑 `backend/.env`，追加（**真值，勿提交，仓库已 gitignore `.env`**）：
   ```
   STRIPE_SECRET_KEY=sk_test_你的密钥
   STRIPE_PRICE_PRO=price_你的价格ID
   STRIPE_WEBHOOK_SECRET=whsec_先留空，下一步 CLI 会给
   ```
2. 启动后端（本机无 uv，用 venv）：
   ```bash
   cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
3. **本地 webhook 转发**（新开终端，需先 `brew install stripe/stripe-cli/stripe` 并 `stripe login`）：
   ```bash
   stripe listen --forward-to http://127.0.0.1:8000/api/v1/billing/webhook
   ```
   - 它会打印 `Ready! Your webhook signing secret is whsec_...` —— 把这个 `whsec_...` 填回 `.env` 的 `STRIPE_WEBHOOK_SECRET`，**重启后端**（让验签密钥生效）。
4. 启动前端：`cd frontend && npm run dev`。

## 三、订阅闭环手验（约 3 分钟）

> 用一个 **plan=free** 的公司、且账号有 `billing.manage` 权限（如 admin）。

1. 前端登录 → 进入**计费/订阅页面**（账户设置内的计费入口）。确认当前显示 **免费版 / free**。
2. 点「升级到 Pro / 订阅」→ 前端调 `POST /billing/checkout-session` → 跳转 Stripe 托管 Checkout 页。
3. 在 Checkout 填 **测试卡**：卡号 `4242 4242 4242 4242`、任意未来有效期、任意 CVC、任意邮编 → 提交。
4. 支付成功后回跳应用。**预期**：
   - `stripe listen` 终端出现 `checkout.session.completed`、`customer.subscription.created/updated` 事件，且后端返回 `200`。
   - 刷新订阅页：plan 变 **pro**、status **active**。
   - 此前被 `require_feature` 锁的 pro 功能解锁（门控放行）。
5. **Portal 退订验回锁**：订阅页点「管理订阅 / 账单门户」→ 调 `POST /billing/portal-session` → 跳 Stripe Customer Portal → Cancel subscription。
   - **预期**：`stripe listen` 出现 `customer.subscription.updated`(cancel_at_period_end) 或 `.deleted`；后端按真相源把 status 置 `canceled`（或周期末），门控随之**回锁**。

## 四、验收清单（逐条打勾）

- [ ] Checkout session 能创建并跳转（无 `STRIPE_SECRET_KEY/PRICE` 配置错）。
- [ ] 测试卡支付成功后回跳。
- [ ] `stripe listen` 收到事件且后端 `200`（**验签通过** —— 若 `400 signature` 说明 `whsec_` 没填对或没重启）。
- [ ] 订阅页 plan=pro / status=active（webhook 同步生效，非前端臆测）。
- [ ] pro 门控功能解锁。
- [ ] Portal 取消后 status→canceled、门控回锁。
- [ ] enterprise 公司（若有）手动设档不被 webhook 改动。

## 五、故障排查

| 现象 | 多半原因 | 处理 |
|---|---|---|
| 创建 checkout 报 500 | `STRIPE_SECRET_KEY`/`STRIPE_PRICE_PRO` 未配或拼错 | 核对 `.env`、重启后端 |
| webhook `400 signature verification failed` | `STRIPE_WEBHOOK_SECRET` 与 `stripe listen` 打印的不一致，或填后没重启 | 用 CLI 打印的 `whsec_` 覆盖、重启后端 |
| 支付成功但 plan 不变 pro | webhook 没到达后端 | 确认 `stripe listen --forward-to` 指向 `…/api/v1/billing/webhook` 且后端在 8000 |
| Checkout 用了真卡被拒 | 没切 Test mode | Dashboard 右上切 Test mode，用 `4242…` |

## 六、收尾

- 手验完成后，**从 `.env` 删掉这三个真值**（或保留在本机；切勿 commit —— `.env` 已 gitignore，`.env.example` 只留占位）。
- 把本次结论记到 [[p6-stripe-billing-mvp]]（手验通过/发现的问题）。

> 关联：实现见 [[p6-stripe-billing-mvp]]；逻辑层测试 `backend/tests/**/*billing*`、`*stripe*`。净室红线见 [[cmms-clean-room-baseline]]。
