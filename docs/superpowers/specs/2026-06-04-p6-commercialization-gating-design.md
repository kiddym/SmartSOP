# P6 商业化 · 门控骨架 设计

> 日期：2026-06-04 · 分支：`feat/p6-commercialization-gating`
> 范围：套餐档位 + 订阅状态机 + 座席上限门控 + 功能门控（按档位解锁）。**Stripe 真实计费（checkout/webhook/订阅同步）留下一轮**，本轮门控骨架是其前置。
> 净室说明：商业化在 Atlas 开源版不存在，本设计**无 parity 基准、为原创设计**，GPL 红线在此自然满足。

## 1. 目标与边界

本轮交付**纯后端门控逻辑 + 配套前端自查/展示页**，不接入任何真实支付。交付后：

- 系统按公司套餐档位限制座席数与高级功能模块的访问。
- platform admin 可手动为公司设档/改订阅状态（模拟"开通"）。
- 公司用户可自查当前档位、座席用量、已解锁功能，并查看三档套餐对比。

**不在本轮**：Stripe SDK/checkout/webhook/订阅同步、发票、trial 自动到期、按用量计费、SSO/API 等 Enterprise 增值项的具体实现（仅在 catalog 留位）。

## 2. 架构总览：feature gate 与 RBAC 正交叠加

引入与权限正交的第二道闸门。任何受限端点的访问需**同时满足**两道闸门：

```
访问受限端点 = require_feature(f) AND require_permission(p)
```

- **RBAC（已有，`app/permissions.py` + `app/deps.py:require_permission`）**：这个**角色**能否做这个操作。
- **Feature gate（本轮新增，`app/deps.py:require_feature`）**：这个**公司的套餐**含不含这个功能模块。

关键不变量：`super_admin` 通配 `ALL_PERMISSIONS`（`role.py:effective_codes`）只绕过 RBAC，**不绕过 feature gate**——套餐没买就是没买，公司内最高角色也不能访问未购模块。

两道闸门**互不知情、可独立测试**：feature gate 只读 `company.plan` / `company.subscription_status`，不碰角色；RBAC 只读角色，不碰套餐。

## 3. 套餐 catalog（硬编码常量）

新文件 `app/billing/catalog.py`，纯常量 + 纯函数，无 DB：

| Plan | 座席上限 | 解锁的高级 feature |
|---|---|---|
| `free` | 3 | （无） |
| `pro` | 15 | PM · METERS · PURCHASING · ANALYTICS · SOP |
| `enterprise` | ∞（无限） | PM · METERS · PURCHASING · ANALYTICS · SOP（+未来 SSO/API，本轮仅留位） |

**5 个 feature 枚举**门控 5 个高级模块 router：

| Feature 枚举 | 门控的 router | 现有端点前缀（参考） |
|---|---|---|
| `FEATURE_PREVENTIVE_MAINTENANCE` | 预防性维护 | `/api/v1/preventive-maintenances` |
| `FEATURE_METERS` | 计量 | `/api/v1/meters` |
| `FEATURE_PURCHASING` | 采购 | `/api/v1/purchase-orders` |
| `FEATURE_ANALYTICS` | 分析仪表盘 | `/api/v1/analytics` |
| `FEATURE_SOP` | SOP / 程序库 / 批量解析 | `/api/v1/procedures` 等 |

**核心模块不挂 feature gate**（所有档都有）：工单、资产、位置、请求、基础库存（备件/库存）、通知、附件、平台基础（用户·角色·团队·公司设置）。

> 门控**粒度 = 整模块**（YAGNI）。模块内细粒度（如"分析里的高级图表/导出"单独门控）本轮不做。

## 4. 订阅状态机

```
plan ∈ {free, pro, enterprise}                         （Python StrEnum，存 String(32)）
subscription_status ∈ {active, trialing, past_due, canceled, suspended}

effective_features(company):
  status ∈ {active, trialing}            → catalog[plan].features        （正常解锁）
  status ∈ {past_due, canceled, suspended} → catalog[free].features      （降级到 Free 功能集）

effective_seat_limit(company): 同上规则
  status ∈ {active, trialing}            → catalog[plan].seat_limit
  status ∈ {past_due, canceled, suspended} → catalog[free].seat_limit = 3
```

**降级语义（用户确认）**：订阅失效后降到 **Free 功能集**——核心模块仍可用，仅锁高级模块；座席上限降到 3，但**仅拦新增、不动存量用户**（见 §5 座席校验）。

**状态来源（本轮）**：无 Stripe 自动驱动。

- 新注册公司默认 `plan='free'` / `subscription_status='active'`。
- 档位/状态变更只经 **platform admin 手动端点**（§5）。
- trial 自动到期、Stripe webhook 驱动的状态流转 → 留 Stripe 轮。

## 5. 数据模型变更（极轻）

Company（`app/models/company.py`）已有占位列 `plan` / `subscription_status`（nullable String(32)，注释 "Reserved billing placeholders (Phase 6)"）。

**本轮不加新列**——座席上限是 catalog 的纯函数，不落库；feature 集亦由 catalog 推导。

迁移 `alembic/versions/YYYYMMDD_NNNN_p6_commercialization_gating.py`（down_revision = `workorder_2b_backfill`，当前 head）：

- backfill 存量公司：`plan='free'`、`subscription_status='active'`（覆盖既有 NULL）。
- 为两列设 `server_default`（`'free'` / `'active'`），使新公司在 DB 层也有默认。
- 可选：加非空约束（backfill 后）。down 还原 server_default 与可空性，可重放。

## 6. 后端组件

| 组件 | 文件 | 职责 |
|---|---|---|
| catalog | `app/billing/catalog.py`（新） | `Plan` / `Feature` 枚举、`PLAN_CATALOG` 常量、`effective_features(company)` / `effective_seat_limit(company)` 纯函数 |
| feature 依赖 | `app/deps.py`（改） | `require_feature(f: Feature)` 工厂依赖；feature ∉ `effective_features(current_user.company)` → **402 Payment Required** |
| 座席校验 | `app/services/invitation_service.py` + 用户创建路径（改） | 创建/邀请前 `active_user_count(company) >= effective_seat_limit(company)` → 402；**仅拦新增、保留存量**（降档超员的存量用户不动） |
| 公司订阅自查 | `app/routers/billing.py`（新） GET `/api/v1/billing/subscription` | 返回当前 `plan` / `status` / 座席 `used`·`limit` / 已解锁 `features` 列表 / 完整三档 `catalog`（供前端套餐对比页）。**读权限：登录即可**（公司内自查，全员可见本公司订阅状态，不新增权限码） |
| platform 设档 | `app/routers/platform.py`（新） PATCH `/api/v1/platform/companies/{id}/subscription` | body：`{plan, subscription_status}`；`require` **is_platform_admin**（非 platform → 403）；校验枚举值；写 Company 两列 |
| 高级 router 挂闸 | PM / meters / purchase_orders / analytics / procedures 各 router（改） | router 级 `dependencies=[Depends(require_feature(...))]`，叠加在既有 `require_permission` 之上 |

**402 vs 403 选择**：feature 未解锁用 **402 Payment Required**（语义=需付费升级，前端据此引导套餐页）；platform 权限不足用 **403 Forbidden**（语义=无权操作）。座席超限用 **402**（需升级扩容）。

**platform admin 识别**：复用现有 `User.is_platform_admin` / `Company.is_platform_admin_org`（探索确认已存在）。platform 端点用一个 `require_platform_admin` 依赖（若已有则复用，否则新增于 `deps.py`）。

## 7. 前端范围（前端从零）

挂在现有导航壳下，纯前端 + 上述新端点对接：

- **订阅/账单设置页**：当前档位徽标、订阅状态、座席用量进度条（used/limit，∞ 特例展示）、已解锁功能清单。数据源 `GET /billing/subscription`。
- **套餐对比页**：三档 catalog 并排对比（座席 + 功能矩阵）；本轮无支付，"升级"按钮 → "请联系管理员"提示（非真实跳转）。
- **模块导航门控**：未解锁的高级模块入口**显示但带锁标**，点击引导到套餐对比页（利于转化、用户感知可升级能力）。门控判定基于 `GET /billing/subscription` 返回的已解锁 feature 集（前端启动时拉取并缓存到 store）。
- **platform 设档 UI**：本轮**不做**（platform admin 是运营角色，用 API/脚本即可）。仅做公司侧自查 + 套餐展示。

前端门控仅为体验层（隐藏/锁标）；**真正的安全边界在后端 `require_feature`**——前端绕过也会被后端 402 拦截。

## 8. 测试策略

沿用 TestClient + 跨租户隔离范式（`tests/conftest.py`、`tests/test_locations_api.py` 范例）。

- **catalog 纯函数**：各 `(plan × status)` 组合 → `effective_features` / `effective_seat_limit` 正确（含失效降级到 Free）。
- **require_feature 依赖**：Free 公司访问 PM 端点 → 402；Pro 公司 → 通过；Pro 但 `past_due` → 402（降级生效）；核心模块端点不受 feature gate 影响。
- **RBAC 正交性**：Pro 公司 + 无 PM 权限的角色 → 403（RBAC 拦）；Free 公司 + super_admin → 402（feature 拦，证明 super_admin 不绕 feature gate）。
- **座席校验**：满员（达 limit）邀请/创建 → 402；降档导致超员后，存量用户仍可登录/操作，新增被拒（保留存量验证）。
- **platform 设档**：非 platform admin → 403；platform admin 设 Pro → 该公司随后可访问高级模块；跨租户（platform 端点按 id 操作，验证普通 super_admin 无法改本公司或他公司订阅）。
- **billing 自查端点**：返回字段完整（plan/status/used/limit/features/catalog），座席 used 计数准确（仅 active 用户）。
- **迁移**：up backfill 既有公司两列 + server_default；down 还原；可重放；`alembic heads` 单 head。

## 9. 实现顺序（供 plan 拆分参考）

1. catalog 常量 + 纯函数（TDD，无依赖，先行）。
2. Company 迁移（backfill + server_default）。
3. `require_feature` / `require_platform_admin` 依赖 + 402/403 语义。
4. 座席校验接入创建/邀请路径。
5. billing 自查端点 + platform 设档端点。
6. 5 个高级 router 挂闸（逐一加依赖 + 回归既有测试不破）。
7. 前端：billing store + 订阅设置页 + 套餐对比页 + 导航锁标。
8. 全量门禁（pytest + ruff + mypy + 前端 test/typecheck/lint）+ 迁移单 head 复核。

## 10. 风险与降级声明

- **JWT 无状态**：订阅状态变更（如平台下调档位）不会即时吊销已签发的 access token；feature gate 在每次请求时实时读 `company.plan`/`status`，故**下一次请求即生效**，无需吊销 token（access 短时、每请求查库）。
- **前端门控非安全边界**：见 §7，安全边界在后端。
- **座席计数口径**：`active_user_count` 仅计 `status='active'` 用户；disabled 用户不占座席。
