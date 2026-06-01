# 批量解析 Word — MVP 设计文档

- 日期：2026-06-01
- 状态：设计草案，待评审（实施计划另立 / writing-plans）
- 取代：本文取代 `docs/batch-parsing-architecture` 分支上的《批量解析 Word 架构设计》草案。原稿大量把"理想中 SaaS 系统"的能力当作"现有可复用基线"，与本项目真实代码严重脱节（详见 §1.2）。本文是对照真实代码库逐条核实后的重写。
- 范围声明：本文是**单期端到端 MVP**——批量上传 → 后台批量解析 → 风险导向审阅 → 批量落库。**不含 AI 解析增强**（另立文档）。多人实时协同、SSE、"记住样式"涟漪、动态标题字典等均为明确非目标（§9）。

---

## 1. 背景与本文定位

### 1.1 核心问题

现有 Word→结构化 SOP 是**单文件**同步流程：前端 `importFromWord()` 串起三步——`POST /uploads`（拿 token）→ `POST /parse`（同步解析，`ThreadPoolExecutor(max_workers=1)` + 30s 超时，跑在 web 进程内）→ `POST /procedures/import`（同步落库）。批量场景（大修前导入历史程序库、迁移上百份 SOP）下这条路径崩在三处：

1. **同步解析阻塞**：N 份大 docx 串行解析把请求拖到分钟级，且占用 web 进程 CPU。
2. **审阅不可扩展**：单文件审阅一次面对一份；几百份没有"风险聚焦 + 批量分流"就是人肉灾难。
3. **落库并发正确性**：多份并发落库的取号、幂等、租户隔离，单文件流程从未面对。

### 1.2 为什么重写（对原稿的批判性审计结论）

对原稿声称的每一处"复用基线"逐条核实后，发现它把**当前代码库根本不存在**的件当作既有基线来复用，导致其篇幅最大的两块章节整体悬空：

| 原稿当作"既有基线" | 真实状态 | 影响 |
|---|---|---|
| 动态标题字典 `HeadingStyleRule` / `HeadingLearningEvent` / "记住此样式" | ❌ 不存在；只有 parser 内部启发式评分 `heading_detector.py`，无持久化学习层、无 `createHeadingRule` | 原稿 §8「记住样式涟漪三目标」整章悬空 |
| `rule_epoch` 租户级版本计数器 | ❌ 不存在 | 原稿 §10 缓存失效机制悬空 |
| `parser_version` | ❌ 不存在 | 同上 |
| `ParseResult` 缓存层（blob/对象存储/Redis） | ❌ 不存在；解析结果从不落库 | 暂存需新建（见 §4） |
| SSE / WebSocket | ❌ 前端零实现，纯请求-响应 | 原稿 §6.6 实时、§11 在场感知悬空 |
| 通用 worker 作业队列 / 泳道池 / 租约领取 | ❌ 不存在；仅单进程 APScheduler 跑 GC/cleanup cron | 原稿 §5 队列调度悬空 |
| 批量上传 UI | ❌ 不存在，纯单文件 | 需新建（见 §6） |

此外两处方法论缺陷：

- **稻草人论证**：原稿 §9.1 用整节警告"若 `sequence_generator` 退化成 `SELECT MAX()+1` 是潜在撞号 bug，须先修"。实际 `sequence_generator.py` 本就是 `FolderSequence` 物化计数器行 + `with_for_update()` 行锁，**从未用过 MAX()**。这是在论证一个不存在的风险。
- **违背自称的 YAGNI**：原稿自称"不预先上分布式队列"，却引入三泳道 worker 池、租户公平调度、aging、背压、single-flight、缓存 blob 分离、claim 租约 + presence + SSE、软撤销窗口——对一个单租户起步、无队列、无缓存、无实时的系统是数量级的复杂度跃升，其中"租户公平"等还在解决当前不存在的需求。

### 1.3 真实可复用基线（已逐条核实存在）

本文据此设计，下列均为**已核实真实存在、可直接复用**：

- **多租户平台**（前置依赖，见 §1.4）：共享表 + `company_id` 行级隔离，靠全局 ORM 事件（`tenant_isolation.py` 的 `do_orm_execute` 自动加 `WHERE company_id=?` + `before_flush` 自动 stamp），**fail-closed**；租户来自 JWT `company_id` claim（`tenant_middleware.py` + `deps.py`）。SOP 表挂 `NullableTenantMixin`。
- **解析管线**：`parser/` 三阶段（`normalize` → `structure`）+ `parse_service._run_with_timeout(data, mode)`（30s 超时），产出 `ParseResult`，其 `ParsedNode` 已带 `confidence` / `confidence_tier`(high|medium|low) / `mark_status` / `heading_source`。
- **落库**：`import_service.import_procedure()`（建 procedure / 节点树 / 重算编号 / asset 提升 / 存源 docx）。
- **取号**：`sequence_generator` 的 `FolderSequence` 行锁计数器（`with_for_update`，非 MAX）。
- **资源**：`asset_service` sha256 内容寻址去重。
- **后台进程**：`app/tasks/scheduler.py` 的 APScheduler `BlockingScheduler`（现跑 GC/cleanup）。
- **节点模型**：`ProcedureNode` 带 `mark_status` / `revision`(乐观锁) / `step_type` / `step_config` / `notice_level`。
- **前端纯原语**：`useVirtualRows`（虚拟滚动）、`buildCascadeSelection`（级联选择）、`arrowNav`（方向键导航）、`isVersionConflict` + E4 reload-wins 冲突恢复、`NodeTreeRow` 渲染、`ImportSideRail`。

### 1.4 前置依赖

本文**以多租户平台为既定基线**。多租户已在 `phase-0-platform-foundation` 分支完整实现，但**尚未合并到主线**。本设计落地前提是该分支已合并；新增表挂 `NullableTenantMixin`，隔离交给现有 ORM 事件，本设计**零手写租户过滤**。注意字段名是 **`company_id`**（非原稿的 `tenant_id`）。

---

## 2. 设计取向

- **两阶段解耦**：parse-stage（CPU、确定性、可重跑、内容寻址可缓存、无副作用）与 apply-stage（落库、取号、有幂等要求）解耦。与现有 `upload→parse→import` 三步天然吻合。
- **纯暂存审阅**：审阅全程发生在**无副作用的暂存层**上，正式库只在最终落库那一刻被触碰一次。由此**原稿 §7「草稿生命周期治理」整块不需要**（没有草稿节点，就没有草稿 limbo / TTL / 隔离视图 / dedup 续审）。
- **最大化复用、最小化新基建**：后台执行复用现有 scheduler 进程；进度用轮询不引入 SSE；取号/落库/资源直接复用现成服务。
- **YAGNI**：租户公平调度、独立 worker 进程池、真并行（ProcessPool）均为非目标，留作显式逃生口。

---

## 3. 总体流程

```
① 批量上传（前端多选 N 份 docx）
      │  后端一次事务：建 BatchJob + N×BatchItem(status=queued)
      │  docx 字节落暂存区（复用现有 upload/source_docx 存储 + sha256）
      ▼
② [scheduler 后台进程] batch_parse_tick 轮询 BatchItem(queued)
      │  进程内受控并发(ThreadPoolExecutor)逐份调用现有 parse_docx()
      │  产出 ParseResult →
      │     · 摘要写入 BatchItem.summary：{confidence_tier, chapter_count, warning_count}
      │     · 完整 ParseResult JSON 写文件系统 blob（按 content_hash 内容寻址）
      │  status=review（失败 → status=failed + error，可重试）
      ▼
③ 审阅台（前端，进度靠轮询，无 SSE）
      │  列表按 confidence_tier 排序/筛选/虚拟滚动
      ├─ 高置信 → 批量直通：从暂存 ParseResult 直接落库
      └─ 低/中置信 → 抽屉速览 / 节点级 diff 改判卡（改判写回暂存 JSON，零副作用）
      │              → 满意后确认落库
      │  落库前：dry-run 影响摘要（N 份新建 / 编号冲突 / 内容重复）
      ▼
④ 落库（唯一有副作用阶段，走后台 apply worker）
      │  per-item 切租户上下文 → 取号(FolderSequence) → import 建 procedure + 节点树
      │  写 created_procedure_id（幂等键）→ status=applied
      ▼
⑤ 清理：批次完成 / TTL 过期 → 复用 cleanup 机制回收暂存 blob + docx
```

两阶段的关键：**parse-stage 无副作用、可重跑、内容寻址可缓存**；**apply-stage 才动库、才取号、才有幂等要求**。

---

## 4. 数据模型与暂存存储

两张新表，严格对齐现有 `models/` 风格（`UUIDMixin` / `TimestampMixin` / `SoftDeleteMixin` / `NullableTenantMixin`，表名 `tb_` 前缀，`DATETIME(6)`，`JSON` 列）。

### 4.1 `tb_batch_import_job`（批次）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | String(36) | UUID |
| `company_id` | String(36) nullable | `NullableTenantMixin`，ORM 事件自动 scope/stamp |
| `folder_id` | FK→tb_folder | 落库目标文件夹（取号前缀来源） |
| `parse_mode` | String(20) | `standard` / `smart` |
| `status` | String(20) idx | `parsing` / `reviewing` / `completed` / `failed`（由 item 聚合，冗余便于列表） |
| `counts` | JSON | `{total, parsed, review, applied, failed}` 冗余计数，供列表 + 轮询 O(1) 读 |
| `created_by` | FK→tb_user | |
| `expires_at` | DATETIME(6) | 暂存 TTL 回收点 |
| `created_at`/`updated_at` | | `TimestampMixin` |
| `is_active`/`deleted_at` | | `SoftDeleteMixin` |

### 4.2 `tb_batch_import_item`（批次内一份文件）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `company_id` | | 同上 |
| `job_id` | FK→tb_batch_import_job idx | |
| `filename` | String(255) | |
| `content_hash` | String(64) idx | docx 的 sha256，内容寻址键 |
| `status` | String(20) idx | `queued`/`parsing`/`review`/`applying`/`applied`/`skipped`/`failed` |
| `summary` | JSON | 反规范化摘要：`{chapter_count, confidence_tier, warning_count}`，列表只读它 |
| `parse_blob_ref` | String idx | 暂存 ParseResult JSON 的存储路径（按 `content_hash` 寻址） |
| `docx_ref` | String | 源 docx 暂存引用 |
| `review_revision` | Integer | **暂存改判的乐观锁**（复用现有 node revision + 409/E4 模式） |
| `created_procedure_id` | FK nullable | **落库幂等键**：非空即已落库，重试直接返回不重建、不烧号 |
| `attempts` | Integer | 解析/落库重试计数 |
| `leased_until` | DATETIME(6) nullable | 租约到期（后台领取/reaper 用，见 §5） |
| `error` | Text nullable | 失败错因（聚合展示用） |
| `reviewed_by` / `reviewed_at` | | 审计 |
| `created_at`/`updated_at`/`is_active`/`deleted_at` | | mixin |

### 4.3 暂存 blob 存储策略

- **摘要 / blob 分离**：列表渲染只读 `summary`（DB 行），**绝不为渲染拉整棵树**；完整 `ParseResult` JSON 存文件系统，路径按 `content_hash` 内容寻址（复用现有 `storage` 模块的 `asset_path` 思路）。
- **内容寻址去重**：同 `content_hash` + 同 `parse_mode` → 跨批复用已存 blob，重传不重解析。
- **审阅改判 = 对 blob 的读-改-写**：人"接受/改判为正文/改判为步骤/调层级"直接重写 blob，受 `review_revision` 乐观锁保护（同一人多标签页并发改判 → 409 → 复用现有 E4 reload-wins）。

### 4.4 两个关键简化（相对原稿）

- **`confidence_tier` / `heading_source` 不持久化到 `ProcedureNode`**——它们天然活在暂存 ParseResult JSON 里（`parser/result.py` 本就产出）。审阅在暂存上做，落库后的节点用现有字段即可。**原稿 §10 的 `rule_epoch`/`parser_version` 缓存失效机制整套不需要**：暂存按内容寻址，没有动态字典涟漪去使它失效，新鲜度等价于"docx 内容没变"。
- 多租户列只挂 `company_id`，隔离交给现有 ORM 事件，本设计零手写过滤。

---

## 5. 后台执行

**载体落地**：在现有 `app/tasks/scheduler.py` 的 `BlockingScheduler` 里**新增两个 `IntervalTrigger` job**，与现有 GC/cleanup cron 并存于同一进程，**无新部署单元**：

- `batch_parse_tick`（如每 5s）：领取并解析 `queued` 项。
- `batch_reaper_tick`（如每 60s）：回收过期租约（崩溃自愈）。

### 5.1 领取 = 短事务 + 租约 + `SKIP LOCKED`

MySQL 8 已确认支持。即便只有单进程，这套仍必要——防 tick 重入、防 job 回调内多 worker 线程取到同一行、并支撑崩溃恢复：

```sql
UPDATE tb_batch_import_item
   SET status='parsing', leased_until=NOW(6)+INTERVAL :ttl SECOND, attempts=attempts+1
 WHERE id = (SELECT id FROM tb_batch_import_item
              WHERE status='queued'
              ORDER BY created_at LIMIT :n
              FOR UPDATE SKIP LOCKED);
```

领取后**在事务外**解析（不把行锁攥在数秒的解析里）；完成后短事务置 `review`。

### 5.2 并发解析

`batch_parse_tick` 回调内用 `ThreadPoolExecutor` 领若干份并发解析，每份**复用现有 `parse_service._run_with_timeout(data, mode)`（30s 超时）**。

> ⚠️ **诚实标注**：python-docx 解析以 CPU 为主，受 GIL 限制，线程并发只能重叠其中的 I/O（解压/XML），CPU 部分不真并行。MVP 起手小并发（`max_workers` 可配，默认 2–4）后台慢跑即可——人审阅时它在后台推进。**逃生口**（本期不实现，仅记录）：吞吐成瓶颈时升级为 `ProcessPoolExecutor` 或独立 worker 进程。

### 5.3 多租户上下文（原稿完全没意识到的陷阱）

后台 scheduler 进程**没有 HTTP 请求、没有 JWT → tenant contextvar 为空**。现有 ORM 事件在 `company_id is None` 时 fail-closed/不加过滤，worker 会查不到数据或写入不被 stamp。解法分两步：

- **领取阶段**用 `tenant.bypass()` 跨租户领作业（worker 是系统级执行者，需服务所有租户的批次）；解析本身是纯 `docx→ParseResult`，**不触碰任何租户数据**，安全。
- **落库阶段**对每个 item 先 `tenant.set_current_company_id(item.company_id)` 进入**该 item 的租户上下文**，再走 `import_service`——这样 ORM 自动隔离与自动 stamp 全部正确。

### 5.4 落库也走 worker

高置信批量直通可能数百份，同步 API 不现实。用户在审阅台点"应用" → item 置 `applying` 入队 → 后台同一套领取机制消费（per-item 切租户上下文 → 取号 → `import_procedure` → 写 `created_procedure_id` → `applied`）。解析与落库**共用领取原语**，只是 `WHERE status IN (...)` 不同。

### 5.5 失败 / 重试 / reaper

- 解析或落库抛错 → `status=failed` + `error` + `attempts++`；审阅台失败聚合 + 批量重试。
- `batch_reaper_tick`：`status IN ('parsing','applying') AND leased_until < NOW()` 的重置回 `queued`/`reviewing`（at-least-once 自愈）；`attempts` 超阈值 → `failed`。
- 落库幂等：取号前在同事务查 `created_procedure_id` 已存在则直接返回——**重试不烧号、不建重复**。

### 5.6 租户公平（MVP 非目标）

MVP 用 `ORDER BY created_at` 单纯 FIFO。原稿的"租户公平调度键 / aging / 背压 / 每租户并发上限"**列为非目标并 `log` 标注**——单进程小并发下 A 租户大批量确会让 B 排队，缓解手段（每租户在跑数上限）留作演进，不预先实现。

---

## 6. 审阅台前端

**前置约束（纯暂存审阅的直接后果）**：审阅对象是**暂存 ParseResult**，不是 `ProcedureNode`。现有编辑器内核（`store/nodeEditor.ts` + node API，绑死 `ProcedureNode`）**不能直接复用**；C 路径"精审"是审阅台**内嵌的结构审阅器**（对暂存 JSON 操作），而非跳转到 `/procedures/:id/edit`（此刻还没有 procedure）。

### 6.1 信息架构 — 风险导向列表

```
顶部汇总条： 待确认 18 · 高置信 156 · 失败 6     ← 每个数字可点即筛
[☐] [状态chip] 文件名.docx        置信   章节  警告   [预览·应用·进精审]
     排队/解析中/待确认/已应用/失败  色条   12    2⚠
```

默认按风险排序（failed→低→中→高→applied），默认筛"仅看待确认"。高置信折叠成一条可批量操作的带子。大列表用 `useVirtualRows` 虚拟滚动。

### 6.2 三条审阅路径

| 路径 | 触发 | 重量 | 适用 |
|---|---|---|---|
| A 批量直通 | 全选高置信 → 应用 | 0 决策/份 | 高置信 |
| B 抽屉速览 | 行内预览 / Enter | 1 眼/份 | 中置信 |
| C 内嵌精审 | 进精审 / Shift+Enter | 逐节点改判 | 低置信 / 有警告 |

处理完一份自动跳下一份待审。

### 6.3 节点级 diff 改判卡（C 路径核心）

写回暂存 blob + `review_revision` 乐观锁：

```
⚠ "3.2 操作步骤" → 识别为 二级章节 (置信 中)
     [接受] [改为正文] [改为步骤] [改为一级]
```

> ⚠️ **去掉了原稿改判卡里的 `[记住此样式]`**——动态标题字典不存在且为非目标。

### 6.4 dry-run 影响摘要（落库前护栏）

调后端 apply-preview：

```
将应用 156 份到「运行程序/一回路」
  · 152 份新建程序  · 3 份编号冲突 → [建新版本]  · 1 份内容重复 → 跳过
预计生成 152 个程序。   [确认应用]  [逐条查看冲突]
```

### 6.5 进度与反馈 = 轮询（无 SSE）

每 3–5s 拉 `job.counts`，列表行随状态刷新；应用 → 行内 spinner → `已应用` chip 带程序链接；失败 toast + 行留原地带 `[重试]`。**软撤销**轻量保留：applied 后短时窗"撤销" → 软删 `created_procedure`（复用现有废止/恢复）。

### 6.6 边界态

全高置信 → 跳过列表直接"全部就绪，确认应用？"；全失败 → 诊断视图；空态。

### 6.7 复用 vs 新写清单

| 复用现有（纯 util/composable，不绑 node store） | 必须新写 |
|---|---|
| `useVirtualRows`（虚拟滚动） | 批量审阅台页面 + 风险列表 |
| `buildCascadeSelection`（级联选择逻辑） | 暂存审阅 store + API（读 blob/改判写回/`review_revision`） |
| `arrowNav`（方向键导航 util） | 节点级 diff 改判卡 |
| `isVersionConflict` + E4 reload-wins 模式 | 抽屉速览（Element Plus `el-drawer`，项目首次使用） |
| `NodeTreeRow` 渲染（需适配暂存数据形状） | dry-run 影响摘要弹窗 |
| `ImportSideRail` / 进度条交互 | 批量多选上传 UI（扩展现有单文件 `CreateFromWordDialog`） |
| | `useBatchReviewShortcuts`（键盘 triage） |

键盘 triage：`↑↓`/`jk` 移动 · `Space` 勾选 · `Enter` 速览 · `A` 应用 · `S` 跳过 · `R` 重试 · `E` 精审。

---

## 7. 后端 API 端点（新增）

对齐现有 `/api/v1` REST 风格，**全部走请求上下文 → 租户隔离自动生效**；后台 worker 不暴露端点。

| 端点 | 作用 |
|---|---|
| `POST /api/v1/batch-imports` | 建批次（`folder_id` + `parse_mode` + `items:[{filename, upload_token}]`，复用现有 `POST /uploads` 拿 token） |
| `GET /api/v1/batch-imports/{job}` | 批次摘要 + `counts`（轮询） |
| `GET …/{job}/items` | item 列表（仅 `summary`，支持 status 筛选/排序） |
| `GET …/items/{id}/parse-result` | 拉暂存 blob（进审阅时） |
| `PATCH …/items/{id}/review` | 改判写回暂存（带 `review_revision`，冲突 409） |
| `POST …/{job}/apply-preview` | dry-run 影响摘要 |
| `POST …/{job}/apply` | 批量应用（`item_ids` 或全选高置信）→ 置 `applying` 入队 |
| `POST …/items/{id}/retry` `/skip` `/undo` | 重试 / 跳过 / 软撤销（短时窗） |
| `DELETE …/{job}` | 放弃批次（软删 + 暂存回收） |

---

## 8. 错误处理、不变量与测试

### 8.1 错误处理矩阵

| 场景 | 处理 |
|---|---|
| 单份解析失败 / 超时(>30s) | 复用 `_run_with_timeout`；`item=failed`+`error`，不影响其它；审阅台聚合 + 重试 |
| worker 崩溃 | `reaper` 回收过期租约 → 重回 `queued`（at-least-once） |
| 落库取号 | `FOR UPDATE` 串行无撞号；`created_procedure_id` 幂等键防重试烧号 |
| 暂存改判并发（同人多页） | `review_revision` 乐观锁 → 409 → E4 reload-wins |
| 内容重复（`content_hash` 命中已 applied） | dry-run 标记，默认跳过 |
| 编号冲突 | dry-run 预览 → 建新版本（复用现有 `upgrade_version`） |
| docx/blob 丢失 | 落库前校验，缺失则重解析或标 `failed` |
| TTL 过期未审 | cleanup 回收暂存 + docx |

### 8.2 关键不变量（实现须守住）

1. **两阶段解耦**：解析无副作用、可重跑、内容寻址可缓存；落库才有副作用与幂等要求。
2. **单一落库写入路径**：批量直通 / 精审定稿都走 `import_service` + `sequence_generator`，无特权旁路。
3. **租约统一 + 跨租户领取/per-item 切上下文**：worker 领作业 `bypass`，处理时 `set(item.company_id)`。
4. **取号无间隙优先**：复用现有 `FOR UPDATE` 计数器 + 一 apply 一锁 + 幂等不烧号。
5. **暂存新鲜度 ≡ docx 内容未变**：内容寻址，无 `rule_epoch`/`parser_version`。
6. **多租户隔离靠现有 ORM 事件**：本设计零手写过滤；API 全在请求上下文，fail-closed。
7. **降级不阻塞**：解析失败 / worker 崩溃均有兜底，用户流程不卡死。

### 8.3 测试策略

沿用项目 pytest + ruff 0.15/mypy 1.20 门禁、SQLAlchemy delete/204/tenant 约定：

- **单元**：租约 `SKIP LOCKED` 不双取；幂等键重试不建重复/不烧号；内容寻址去重；改判乐观锁 409；reaper 回收。
- **集成**：端到端批次（上传 N→后台解析→改判→落库）；并发落库同文件夹不撞号。
- **对抗**：两租户批次互不可见 + IDOR；worker `bypass` 领取不泄漏跨租户数据；落库 per-item 正确 stamp `company_id`。

---

## 9. 明确非目标（MVP 不做）

文档显式声明，以划清边界：

- 多人实时协同 / claim / presence（原稿 §11）
- SSE / WebSocket 实时推送（用轮询替代）
- 记住样式涟漪 / 动态标题字典 / `HeadingStyleRule`（原稿 §8，依赖不存在的 roadmap）
- `rule_epoch` / `parser_version` 缓存失效（本设计不需要）
- 草稿生命周期治理 / materialize 草稿节点（纯暂存审阅下不存在）
- 租户公平调度 / aging / 背压 / 块分配取号（YAGNI，FIFO 起步）
- 独立 worker 进程池 / `ProcessPool` 真并行（逃生口，本期不实现）
- AI 解析增强（另立文档）

---

## 10. MVP 内部实现顺序建议（细化留给 writing-plans）

1. 数据模型 + 迁移（`BatchJob` / `BatchItem`）
2. 批次创建 API + 后台 `batch_parse_tick` + `batch_reaper_tick`（跑通解析→review）
3. 审阅台只读列表 + 轮询 + 抽屉速览
4. 节点级 diff 改判 + 暂存改判 API + `review_revision` 乐观锁
5. dry-run `apply-preview` + apply worker + 幂等落库
6. 失败聚合 / 重试 / 软撤销 / 边界态

依赖：① → ② → (③ ∥ ④) → ⑤ → ⑥。前置：`phase-0-platform-foundation`（多租户）已合并。
