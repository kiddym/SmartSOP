# Word 解析与动态字典 —— 整合进多租户主线 · 统一设计（spec）

> **日期**：2026-05-31
> **状态**：待评审 → 转 writing-plans
> **目标分支基准**：`phase-0-platform-foundation`（主线，已具租户根 + ORM 事件隔离）
> **整合来源**：`feat/dynamic-heading-dictionary`（动态字典 M1–M4b + parser P0/P1 修复，**无租户**）
> **取代关系**：本 spec 取代 `docs/superpowers/plans/2026-05-31-saas-parser-tenant-evolution.md` 的 DEP-0 部分——
> 该文档 §9.1「tenant 根不存在」的前提**对主线不成立**（详见 §2）。

---

## 0. TL;DR

产品是一个内含 SOP/程序文档模块的 CMMS。当前有两条分叉分支：

- **主线** `phase-0-platform-foundation`：完整 CMMS + SOP 模块（procedure/node/folder/parser），**已具备成熟的多租户根 + ORM 事件级行隔离**（`company_id`），但**没有动态标题字典**。
- **parser 线** `feat/dynamic-heading-dictionary`：动态字典自学习 M1–M4b + parser 准确率 P0/P1 修复 + 归因字段下穿，但**完全无租户**，且这些文档（4 份）写于此线、误以为"租户根不存在"。

**统一任务**（重新定性）：把 parser 线的成果**移植进主线**，三张新表复用主线既有的 `NullableTenantMixin` + ORM 事件隔离，使其"天生多租户"；无须从零建租户根。工程主轴从"解析得多准"转为"每个租户多快学会他的模板、且彼此绝不串户"。

---

## 1. 目标与范围边界

### 范围内（本 spec 拥有）

| 块 | 内容 |
|---|---|
| **A. 动态字典移植** | 把 `heading_rule` / `numbering_profile` / `heading_learning_event` 三表 + service + router + 前端，从 parser 线移植进主线 |
| **B. parser 修复对齐** | 同 commit 打包的 P1 跨 numId 修复（`_assign_styled_depths`）+ 归因字段下穿（`source_style_name` / `source_numbering_pattern`）一并移植 |
| **C. 三表租户化** | 三表加挂 `NullableTenantMixin`（得 `company_id`）；唯一约束改复合 `(company_id, style_name)` / `(company_id, pattern_key)`；事件表加 `company_id` + 复合索引 |
| **D. 投票/注入分区接缝** | 验证并修补：投票聚合 `reaggregate`、注入 `active_*_overrides`、IDOR 直取入口在 ORM 事件下确实按 `company_id` 分区（多数自动，列出需显式验证/补洞项，见 §5）|
| **E. 同义词分层** | `heading_synonyms.yaml` 作平台默认底座 + 租户覆盖（复用 `heading_rule` 的 manual/learned，**不新建表**）|
| **F. 内部重构 + 前端边界** | ResolverChain / NumberingProfile 收口（纯内部）；前端 scope/provenance 标识、复查面板按租户隔离、复查吞吐打磨 |
| **G. Phase 1 / Phase 2** | SaaS MVP（onboarding 向导、配置自助、平台运营面、import 快照锁）；规模化（触发才做）|

### 范围外（明确不做）

- ❌ 从零建租户根 / `Tenant` 表 / `tenant_id` 列 / header dependency —— **主线已有**（`company_id` + `TenantScoped` + ORM 事件 + `tenant_middleware`），直接复用。
- ❌ 重写解析器、上 LLM 端到端、引 pandoc/mammoth（三方共识已否决）。
- ❌ 完整登录/鉴权/计费体系（另立项；本 spec 只消费既有租户上下文）。
- ❌ Phase 2 中心化分类器的实际训练（仅留插槽 + 触发条件）。

### 作为不可回归基线接收（不重做，只固化回归门，见 §3）

- 动态字典自学习 M1–M4b（parser 线已实现）
- parser 准确率 P0（顿号子节）/ P1（跨 numId 层级）修复
- 主线既有的租户隔离行为（CMMS 全量 + SOP 表 `NullableTenantMixin`）

---

## 2. 现状：两分支真实关系（本 spec 的事实基准）

### 2.1 主线已具备的租户能力（= 4 份文档误以为不存在的 DEP-0）

| 设施 | 落点 | 说明 |
|---|---|---|
| 租户标记 + mixin | `models/base.py`：`TenantScoped` / `TenantMixin`(NOT NULL) / `NullableTenantMixin`(nullable) | 租户维度 = **`company_id`** |
| ORM 事件隔离 | `tenant_isolation.py`：`before_flush` 自动盖 `company_id`；`do_orm_execute` 用 `with_loader_criteria` 给所有 SELECT 自动加 `company_id` 过滤 | 注册在全局 `Session`，app + tests 全覆盖 |
| 请求级租户上下文 | `tenant.py`（`get_current_company_id` / `is_bypassed`）+ `tenant_middleware.py` | 纯 ASGI 上下文 |
| SOP 表已挂租户 | `procedure` / `node` / `folder` / `source_docx` / `field` / `settings` 用 `NullableTenantMixin` | base.py 注释：「SOP tables (Phase 0): company_id nullable; **enforcement deferred to Phase 1**」——平台团队已预留 |
| CMMS 平台表 | work_order / asset / meter / part / pm / request / vendor / customer / location / team / user / role… 用 `TenantMixin` | company_id NOT NULL |

> 与你曾在该项目使用的租户隔离架构（中间件 + ORM 事件 + 纯 ASGI 上下文）一致——本 spec 直接站在它之上。

### 2.2 主线缺什么、parser 线有什么

| 能力 | 主线 `phase-0-platform-foundation` | parser 线 `feat/dynamic-heading-dictionary` |
|---|---|---|
| 租户根 + ORM 隔离 | ✅ 有 | ❌ 无 |
| 动态字典三表 + 自学习 M1–M4b | ❌ 无 | ✅ 有 |
| parser P0 顿号修复（`depth >= 2`）| ✅ 有 | ✅ 有 |
| parser P1 跨 numId 修复（`_assign_styled_depths`）| ❌ **无** | ✅ 有 |
| 归因字段 `source_style_name` / `source_numbering_pattern` | ❌ **无** | ✅ 有 |

**结论**：P1 修复 + 归因下穿 + 动态字典三件，在 parser 线是**同一 commit（`63750b6`）打包**的，必须**一起移植**；移植后三表加挂 mixin 即获租户隔离。

### 2.3 移植口径（避免"反向丢失"主线工作）

移植 = 把 parser 线的**增量**叠加到主线，**不得**回退主线的 CMMS / 租户 / SOP-租户化工作。具体地：对 `node.py` / `procedure.py` / `parser/` 这些**两线都改过**的文件，采用"在主线版本上**增量打补丁**"而非"用 parser 线版本覆盖"（parser 线版本不含 `NullableTenantMixin` 等主线改动）。

---

## 3. 不可回归基线与回归门

任何阶段完成后必须重跑并保持绿。

### 3.1 解析准确率门（移植后必须复现）

| 文档族 | 期望层级分布 | 含义 |
|---|---|---|
| 标准样式 4 份（公司运营管理 / _表格图片 / 电厂管理巡视规定 / 1_程序模板）| 与真值一致 | 零回归红线 |
| TP试验程序（扁平样式 + 跨 numId）| `{1:29, 2:11, 3:3}` | **P1 移植成功的判据**（主线当前缺 P1，移植后必须达到）|
| 顿号子节文档（12/17/18/22 号等）| 恢复 2–3 级 | P0 基线 |
| 危险源 / 有限空间（depth=1 顿号 / 第X条）| 维持单层、不误升 | P0 不过度升级 |

### 3.2 第 0 步——常驻准确率回归脚本（前置基础设施）

parser 线的 `eval_parser.py` / `eval_tree.py` 是一次性、已删除。本 spec 把"**固化一个常驻准确率回归脚本**"作为整合的**第 0 步**：对 36 份样本统计层级分布并与 §3.1 基线断言比对，纳入 CI/手动回归。否则租户化横切 + 移植打坏解析层级无人察觉。

### 3.3 自学习三道护栏（移植后在租户内重新闭合）

1. 投票阈值 `K_DOCS=3` + `MIN_AGREEMENT=0.8`（防 n=1）
2. 归因粒度护栏：每文档投 1 票 = 该样式主导终态层级（TP 23:1 不翻 `章节标题=L1`）
3. 异常哨兵 + 矛盾降级（`_looks_like_prose`；active 规则 agreement 跌破阈值自动降 candidate）

口径不变，仅统计范围由"全局"收窄为"单租户（按 `company_id`）"。

### 3.4 保真不变量（红线）

1 段落 ↔ 1 IR 块 ↔ 1 节点；内容 0 改写；C001–C006 对账；HIGH 自动 / MEDIUM 预标 / LOW 候选 + 模式批量 + 样式记忆。

### 3.5 主线既有测试门

主线 CMMS + SOP 既有测试套件、parser 单测全绿；移植**不得**使主线任何既有测试退化（含租户隔离用例）。

---

## 4. 整合架构

### 4.1 动态字典三表加挂租户 mixin（C 的核心）

| 表 | 当前（parser 线）| 整合后（主线）|
|---|---|---|
| `tb_heading_style_rule` | `Base, UUIDMixin, TimestampMixin, SoftDeleteMixin`；`style_name unique=True` | **+ `NullableTenantMixin`**（得 `company_id`，与 SOP 表同档）；`uniq(style_name)` → `uniq(company_id, style_name)` |
| `tb_numbering_profile` | 同上；`pattern_key unique=True` | + `NullableTenantMixin`；`uniq(pattern_key)` → `uniq(company_id, pattern_key)` |
| `tb_heading_learning_event` | 裸 `Base`，BIGINT pk，append-only | + `NullableTenantMixin`（`company_id`）+ 复合索引 `(company_id, style_name)` |

加挂 `NullableTenantMixin` 后，**插入自动盖 `company_id`**（`before_flush`）、**SELECT 自动按 `company_id` 过滤**（`do_orm_execute`）——这正是原 §3/§4 要手工实现的隔离，主线**已经免费提供**。

> mixin 选择：与同属 SOP 模块的 `procedure`/`node` 一致用 `NullableTenantMixin`（Phase 0 nullable、Phase 1 收紧），保持架构一致；不破坏 base.py 注释承诺的演进节奏。

### 4.2 解析优先级（移植后完整链，向下兼容）

```
手动钉死(manual·租户) > 学习生效(learned active·租户) > 租户同义词覆盖
  > 平台默认同义词(yaml) > outlineLvl > basedOn
```

零样式文档仍走 L3 启发式封顶 0.84、永不自动 HIGH。

### 4.3 同义词分层（E，复用 heading_rule、不新建表）

`heading_synonyms.yaml` 降级为平台默认底座；**租户覆盖复用 `tb_heading_style_rule` 的 `manual`/`learned`**（租户级"样式名→层级"规则）。解析时合并、租户优先。验收：同一样式名在租户 A 解析为 L1、租户 B 为 L2，互不影响（天然由 `company_id` 隔离）。

---

## 5. 解析线接缝（投票分区 / IDOR —— 多数自动，列出需验证/补洞项）

主线 ORM 事件隔离覆盖"常规 SELECT 与 flush"。以下接缝**必须显式验证**，证伪则补：

| 接缝 | 期望 | 验证/补洞 |
|---|---|---|
| **投票聚合** `heading_learning_service.reaggregate` | 事件表 SELECT 在租户上下文下自动加 `company_id` → 投票只统计本租户 | **必须验证** `do_orm_execute` 对该聚合查询（含 `func.count`/`group_by`）生效；若聚合走了绕过事件的路径，则显式加 `company_id` 过滤 |
| **IDOR 直取** `get_or_404`（`db.get`）/ `_get_node` / `get_nodes` / `batch_update` / `reorder` | 跨租户 id → 查不到/404 | **必须验证** `do_orm_execute` 是否覆盖 `Session.get()`（SA 2.0 多数覆盖）；不覆盖处改用带 criteria 的 query 或显式归属校验 |
| **注入** `active_style_overrides` / `active_numbering_overrides` | 只拼本租户 active 规则 | 普通 SELECT，自动分区；加用例固化 |
| **学习钩子** `node_service._learn_from_edit` → `observe_node_edit` | 写事件时 `company_id` 自动盖（node 自带）| `before_flush` 自动；验证 node 的 `company_id` 已落 |
| **解析路径** `parse_service.parse` | 在租户上下文内运行 | 确认请求经 `tenant_middleware`；非请求路径（脚本/任务）需 `tenant.bypass` 或显式 company |

> 设计取向（呼应你"service 层够了"的偏好）：**优先依赖既有 ORM 事件自动隔离**，仅对事件覆盖不到的路径（聚合、`get()`、后台任务）做显式补洞，不再额外铺一层 service 包装。

### 5.1 测试矩阵

- 更新既有调用签名（移植带入的 service）。
- 新增：两租户同名样式**互不投票、互不覆盖**；跨租户 id 访问→查不到/404；同义词分层不同 level。
- 回归：§3 全部门重跑保持绿（单租户 = 单一 company 路径行为不变）。

---

## 6. 内部重构 + 前端边界

### 6.1 ResolverChain 重构（纯内部，零行为变化）

把 `styles.classify_with_source` 的 Tier-2 启发式封装为显式责任链 `[StyleResolver, SynonymResolver, OutlineResolver, HeuristicResolver]`，对外 API 不变。收益：Phase 2 分类器只替换 `HeuristicResolver` 一个插槽。验收：parser 单测逐字节零退化。

### 6.2 NumberingProfile 解析侧收口（纯内部）

散落 `_RE_*` 收进 `NumberingProfile` 对象，预留 `load_profile_for(company_id)` 入口。验收：解析行为逐字节不变。

### 6.3 前端平台/租户边界

| 维度 | 改造 |
|---|---|
| **scope** | 规则/profile 标注 `platform-default` / `tenant`；`HeadingRule` interface 已有 `source`，**补 `scope`** |
| **provenance** | 可视化 `source`：`platform-default`（只读、不可删、只能覆盖）/ `manual` / `learned`（护城河体验化）|
| **可见性** | 租户只见自己 + 平台默认（只读）；ORM 事件保证数据层不串户 |

两类面：**租户自助面**（扩展现有 `HeadingRulesView` + 编号体例友好配置 + 复查面板按租户隔离）；**平台运营面**（Phase 1 才做：平台默认底座、跨租户收敛曲线看板）。

### 6.4 复查吞吐打磨（主轴 B，SaaS 下 ROI 最高，非 parser 精度）

模式批量分组勾选、键盘流、样式记忆预热、迁移批次"一次配置多文档复用"。验收：迁移一份零样式文档操作次数较基线下降，截图佐证。

---

## 7. Phase 1 / Phase 2 + 红线 / KPI

### 7.1 Phase 1 —— SaaS MVP

全链路租户隔离落地（SOP 表由 nullable 收紧为强隔离，兑现 base.py 承诺）；导入做成 onboarding 向导；编号体例配置自助 UI（主轴 C：新客户 = 一条配置）；平台运营面（跨租户健康看板 + 每租户收敛曲线 KPI）；**import 即快照补锁**（parse 时把 `rule_revision` 快照进草稿，import 校验；`heading_rule` 已有 `revision`，成本极低）。

### 7.2 Phase 2 —— 规模化（触发才做）

触发条件：正则维护成本超线，**或**上线首个非中文 / 非 SOP 客户。用 `tb_heading_learning_event`（append-only 全租户纠偏 = 天然标注集）训中心化 heading 四分类器，替换 `HeuristicResolver`（复用 §6.1 插槽）。守红线；只补 L3 冷启动，不接管 L0/L1/L2。

### 7.3 红线

1. 保真不变量不松动。2. 模型只判 heading，永不碰内容序列化。3. 模型/数据不跨租户泄露（Phase 2 共享分类器只用脱敏/聚合特征，原文不出租户边界）。4. 不为单客户改主干正则、不发版——特例走配置/学习。5. 任何按 id/procedure_id 的读写必须按 `company_id` 隔离（依赖 ORM 事件 + §5 补洞）。

### 7.4 精度 KPI —— 每租户收敛曲线

衡量"新租户从第 1 份到稳定态需几份纠偏"（收敛步数），非全局平均 P。

---

## 8. 阶段顺序与测试策略

```
第 0 步：常驻准确率回归脚本（§3.2，解锁安全推进）
  │
Phase 0  ├─ 移植 A+B：动态字典三表 + service/router/前端 + P1 修复 + 归因下穿（增量打补丁，§2.3）
         ├─ 租户化 C：三表加挂 NullableTenantMixin + 复合唯一约束 + Alembic 迁移
         ├─ 接缝 D：§5 投票分区 / IDOR 验证与补洞
         ├─ 同义词 E：平台默认 + 租户覆盖（复用 heading_rule）
         └─ 重构 F：ResolverChain / NumberingProfile（并行，纯内部）+ 前端 scope/provenance
  │
Phase 1  SaaS MVP（§7.1）
  │
Phase 2  规模化（触发才做，§7.2）
```

测试策略：回归门（§3）每阶段后重跑；隔离用例（两租户互不串）；IDOR 用例（跨租户→404）；迁移用例（复合唯一 + downgrade 可逆，**SQLite 改约束须 `batch_alter_table` 重建表**）；重构零退化（parser 单测逐字节一致）；收敛验证（重放脚本统计 `review_required` 下降曲线）。

---

## 9. 开放验证项与风险

| 项 | 风险 | 处置 |
|---|---|---|
| **两分支移植冲突** | `node.py`/`procedure.py`/`parser/` 两线都改，直接 cherry-pick `63750b6` 可能冲突 | 增量打补丁（§2.3）；移植后立即跑 §3 回归门 |
| **`do_orm_execute` 覆盖面** | 聚合查询 / `Session.get()` 可能绕过事件 → 投票串户 / IDOR 漏 | §5 显式验证；证伪则补 `company_id` 过滤（这是本 spec 唯一可能"自动隔离失效"的点，需最先验证）|
| **后台/脚本路径无租户上下文** | 解析任务在请求外运行 → `company_id` 为 None | 明确 `tenant.bypass` 或显式传 company 的约定 |
| **SOP 表 nullable 期的语义** | Phase 0 `company_id` 可空 → 历史/默认数据 company_id=None 时 ORM 事件不过滤（`is None` 短路）| 与主线既有 SOP 行为一致；Phase 1 收紧时统一回填 |
| **P1 移植判据** | 主线缺 P1，移植后 TP 必须达 `{1:29,2:11,3:3}` | 作为移植成功的硬验收 |

---

## 10. 参考

- 取代/上游：`docs/superpowers/plans/2026-05-31-saas-parser-tenant-evolution.md`（DEP-0 前提对主线不成立）
- 动态字典设计：`docs/reference doc/动态标题字典与自学习方案.md`（M1–M4b 实现记录）
- 准确率基线：`docs/reference doc/解析器准确性评估报告_20260531.md`（P0/P1 修复记录）
- 租户设施（主线）：`backend/app/models/base.py`、`tenant_isolation.py`、`tenant.py`、`tenant_middleware.py`
- 动态字典源（parser 线）：`origin/feat/dynamic-heading-dictionary` 的 `models/{heading_rule,numbering_profile,heading_learning_event}.py`、`services/heading_*`、`routers/heading_rules.py`、`views/settings/HeadingRulesView.vue`
- 解析方案：`docs/word-parser-solution.md`、`docs/parser-comprehensive-evaluation.md`
