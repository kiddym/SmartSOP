# 设计：资产补全 ③（停机树传播 + 自动停机触发）

- 日期：2026-06-02
- 范围：后端净室原创，资产停机树**持久级联（向下为主）** + **状态驱动的自动停机触发**
- 分支：feat/asset-backfill（独立 worktree，基于 main 104c3a2；与分析补全 feat/analytics-backfill 并行、文件不重叠）
- 基线约束：净室原创（仅参照通用 CMMS 停机/可用率功能行为，绝不复制 Atlas 代码/DDL/文案/命名；产品不出现 "Atlas"；GPL 合规）；仅中文、不做 i18n；后端解释器统一 `backend/.venv/bin/python`；门禁 ruff 0.15 + mypy 1.20；pytest 用 SQLite `Base.metadata.create_all`

## 1. 背景与目标

现状（核实于本 worktree）：

- `Asset`（`tb_asset`，maintenance_asset.py）有 `parent_id` 树、`status`（`AssetStatus`）、`location_id`/`category_id`。
- `AssetStatus`（asset_status.py）已定义 `UP_STATUSES`/`DOWN_STATUSES` 分类（注释"供 Phase 4 可用率复用"）。
- `AssetDowntime`（asset_downtime.py，docstring 自承"无树传播，Phase 4 再做"）：`asset_id`/`started_at`/`ended_at`/`reason`/`downtime_type`（默认 "manual"）。
- `maintenance_asset_service.py`：`update_asset` 改 `status` 为**纯字段写、无副作用**；`add_downtime`/`close_downtime`/`list_downtimes` 为手动流；`_descendant_ids(db, asset_id)` 已存在（BFS 收全部 active 后代）；`list_children`/`_validate_parent` 已就绪。
- 状态变更经 PATCH `/{asset_id}`（`update_asset`），无独立状态端点。

**Gap（本轮补）**：停机树**向下持久级联** + **自动停机触发**（status→DOWN 自动登记停机，→UP 自动关闭）。

**不补（留后续）**：折旧 Deprecation、平面图 FloorPlan（低优先）；祖先可用率"向上读时聚合"属分析改动且与分析补全文件冲突（见 §6），移出本轮。

## 2. 模型变更：`AssetDowntime` 加两列

- `source_asset_id` `Mapped[str | None]`，`String(36)`，FK→`tb_asset.id` `ondelete=SET NULL`，index，nullable。级联记录指向触发的祖先资产；自发（auto）记录为 `None`。
- `prior_status` `Mapped[str | None]`，`String(20)`，nullable，default None。级联导致后代状态变更时记录其原状态，恢复时还原。
- `downtime_type` 既有 `String(20)`；取值约定扩为 `manual` | `auto` | `cascade`（不改列定义，仅语义扩展）。

## 3. 行为规格（全部由 `update_asset` 的状态跃迁驱动）

入口：`update_asset` 检测 `status` 旧值→新值，按 `UP_STATUSES`/`DOWN_STATUSES` 归类。仅当跃迁跨越 UP↔DOWN 边界时触发副作用（UP→UP、DOWN→DOWN 内部切换不触发）。

抽公共函数 `apply_status_transition(db, asset, old_status, new_status, company_id)`，被 `update_asset` 在 setattr status 后调用。

### 3.1 UP → DOWN（资产 A）

1. 给 A 建一条 open 自动停机：`{asset_id:A, downtime_type:"auto", source_asset_id:None, started_at:utcnow(), ended_at:None, prior_status:None}`。
2. 向下级联：遍历 `_descendant_ids(db, A.id)`（全部 active 后代）。对每个后代 D（按 id 取 Asset）：
   - D 当前 UP：记 `prior=D.status`，置 `D.status=AssetStatus.DOWN`，建 `{asset_id:D, downtime_type:"cascade", source_asset_id:A.id, prior_status:prior, started_at:now, ended_at:None}`。
   - D 当前 DOWN：仅建 `{asset_id:D, downtime_type:"cascade", source_asset_id:A.id, prior_status:None, started_at:now, ended_at:None}`（记依赖、不改状态）。

### 3.2 DOWN → UP（资产 A 恢复）

1. 关闭 A 的所有 open 自发停机（`asset_id:A` 且 `source_asset_id is None` 且 `ended_at is None` 且 `downtime_type in {auto}`）：`ended_at=now`。
   - 注：手动 open 停机（type=manual）**不**被自动关闭（见 §4 解耦）。
2. 关闭所有 `source_asset_id == A.id` 且 `ended_at is None` 的 cascade 记录：`ended_at=now`。
3. 对步骤 2 涉及的每个后代 D：重新查 D 是否仍有任何 open 停机（任意 type，`ended_at is None`）。
   - 无：还原 `D.status` 到该后代本次关闭记录中非空的 `prior_status`（若多条取最早一条的 prior；皆 null 则 `AssetStatus.OPERATIONAL`）。
   - 有：维持 DOWN（D 另有独立停机原因）。

### 3.3 不变量与嵌套

- **不变量**：自动/级联管理下，资产处于 DOWN 状态 ⟺ 至少一条 open 停机记录归属它。
- 嵌套树（A→B→C）：`_descendant_ids(A)` 一次收全 {B,C}，逐个独立记账；反转按 `source_asset_id` 精确闭合，互不干扰。
- 已知局限（v1 文档化）：若用户在 A 停机期间手动改动后代 D 的 status，反转还原可能与用户意图不符；多祖先共享后代的并发独立停机为罕见场景，按"D 仍有 open 停机即维持 DOWN"规则保守处理。

## 4. 手动停机解耦（明确决策）

`add_downtime` / `close_downtime` 维持现状：**不**改 `Asset.status`、**不**级联。"自动停机触发"特指 status→DOWN 时自动补登记一条 `auto` 停机供可用率统计。手动停机用于补录/独立记录区间，与当前状态解耦。

理由：手动停机常用于补录历史区间，不应强改当前状态；语义清晰、低风险、不破坏既有手动停机测试。

## 5. 端点与 schema

- **无新端点**。行为内嵌于既有 PATCH `/{asset_id}`（`update_asset`）。
- `DowntimeRead` 暴露 `source_asset_id: str | None` 与（既有）`downtime_type`，便于前端区分自动/级联/手动。
- `DowntimeCreate` 不变（手动创建仍只接受 started_at/ended_at/reason/downtime_type；`source_asset_id`/`prior_status` 仅服务内部写）。

## 6. 与分析补全（group ⑤）的边界与协调

并行的分析补全 agent 正改 `app/services/analytics/asset_reliability_analytics.py`（资产可用率）。本轮 **③ 不得修改任何 `app/services/analytics/` 或 `app/routers/analytics.py` 文件**。

- 后代经级联获得真实 `AssetDowntime` 记录 → 其**自身**可用率（现有 asset_reliability 按本资产停机区间算）已自动正确，无需改分析。
- 祖先可用率"按后代停机向上读时聚合"= 分析层增强，**移出 ③**，记为后续分析子轮。

**迁移 down_revision 协调点**：分析补全的迁移 `analytics_backfill` 与本轮迁移都以 `workorder_labor_cost` 为 down_revision（各自分支独立）。两分支合入 main 时**后合入者必须 rebase 其迁移的 down_revision** 指向先合入者的 revision，形成单一线性链。spec/plan 标注；实现期保持 `down_revision="workorder_labor_cost"`，合并时按实际落地顺序由人协调改链（迁移 unit 测试只验 DDL up/down，不依赖链顺序）。

## 7. 横切

- 权限：复用 `asset.edit`；无新权限。
- 多租户：`AssetDowntime` 已挂 `TenantMixin`；`_descendant_ids` 经 ORM 自动 company scope，级联只在同租户内。跨租户对抗必测（A 公司资产树级联不波及 B；他租户 asset_id 不可作 source）。
- 金额/时间：无金额；时间用 `utcnow()`。
- 净室原创、仅中文。

## 8. 测试策略

SQLite in-memory（conftest fixture）：

- **自动触发**：UP→DOWN 建 open auto 记录；DOWN→UP 关闭之；UP→UP / DOWN→DOWN 不触发。
- **向下级联**：父 DOWN → 后代（多层 A→B→C）全部置 DOWN + 各得 cascade 记录（source=父）；父恢复 → 后代还原到 prior_status。
- **解耦反转**：后代有独立 open 停机（manual 或另一 source 的 cascade）时，父恢复**不**把它拉回 UP。
- **手动解耦**：`add_downtime` 不改 status、不级联（守住现状）。
- **prior_status 还原**：后代原为 STANDBY，级联→DOWN，反转还原回 STANDBY（非 OPERATIONAL）。
- **跨租户**：A 公司父停机级联不触及 B 公司同结构资产。
- **迁移**：`tests/unit/` 单测（importlib + MigrationContext，最小 tb_asset 父表）验 add_column/drop_column up/down。
- 纯函数（状态归类判断、级联记账）尽量可独立单测。

全量回归 + `ruff check app/` + `mypy app/` 每任务绿后提交。

## 9. 任务切分（供 plan 细化）

1. **模型加列**：AssetDowntime + source_asset_id + prior_status；`DowntimeRead` 暴露 source_asset_id；注册无新模型（同表加列）。
2. **自动停机触发**：`apply_status_transition` 公共函数 + UP→DOWN 建 auto / DOWN→UP 关 auto；`update_asset` 接线（捕获 old_status）。
3. **向下级联 + 反转**：级联建 cascade 记录 + 后代状态写；反转闭合 + prior 还原（含"仍有 open 则维持"规则）。
4. **跨租户与边界测试**：对抗测 + 手动解耦回归。
5. **迁移**：tb_asset_downtime 加两列 + unit 测试 + up/down 可重放（down_revision="workorder_labor_cost"，合并协调见 §6）。

> 任务 2 依赖 1（列就绪）；3 依赖 2（公共函数）；5 末位。

## 10. 不在本轮

- 折旧 Deprecation、平面图 FloorPlan（低优先，留后续）。
- 祖先可用率向上聚合（分析层，移出 ③，见 §6）。
- 手动停机与状态联动（本轮明确解耦，§4）。
