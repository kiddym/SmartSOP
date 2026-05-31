# Word 解析与标注 —— SaaS 多租户演进方案（执行 plan）

> **版本**：v2（2026-05-31）
> **状态**：待执行（交接给"正在做 SaaS 化"的 agent）
> **载体**：本文档自包含，无需本对话上下文即可冷启动执行。
> **前置上游**：本 plan 覆盖**解析器 / 标注 / 动态字典**这条线在 SaaS 下的改造。
> ⚠️ **v2 修正**：经依赖追踪确认，`tenant_id` 的"根来源"当前**全系统不存在**
> （见 §9.1），本线**强依赖** SaaS 主线先建立"租户根 + 请求级 tenant 上下文"。

### 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-05-31 | 初版：三方共识、两处硬伤、三主轴、Phase 0 六任务 |
| **v2** | 2026-05-31 | 新增 §4.5 多租户 parser 精度模型（L0–L3 + 收敛曲线 KPI + import 快照 + "L0 非模型"澄清）；新增 §8 前端平台/租户边界；新增 §9 依赖变动与影响边界评估（含 tenant 根缺失结论、IDOR 越权横切风险、影响矩阵、修正依赖顺序）；§3、§6 相应扩充 |

---

## 0. TL;DR

系统未来要做成 **SaaS：多租户、每家公司有自己的 Word 模板**。这把工程主轴从
"解析得多准"换成 **"每个租户多快学会他的模板、且彼此绝不串户"**。

- **不重写解析器、不上 LLM 端到端、不引 pandoc/mammoth**（理由见 §2）。
- 精度靠**分层**（§4.5）：L0 样式（全局免费高精度，**是确定性规则，不是模型**）
  + L1/L2（每租户学习/配置）+ L3（通用兜底封顶）。
- 现有"纠偏→投票→动态字典"学习闭环（M1–M4b）是 SaaS 护城河，但现在是**单租户**，
  且有串户/越权硬伤（§3）。
- **关键前提（v2）**：`tenant_id` 根来源当前不存在（§9.1），解析器三表租户化是
  "全系统多租户化"的子集，**有前置依赖**。可独立先做的是"留缝"重构（§9.5）。

---

## 1. 不可回退的事实（决定方案走向）

| 事实 | 来源 | 影响 |
|---|---|---|
| 未来做 SaaS，多租户 | 用户确认（2026-05-31） | 数据/规则/学习必须按租户隔离 |
| 每家公司有**自己的 Word 模板** | 用户确认 | 模板随客户**无界增长**，调参跑步机从风险变必然 |
| 单租户导入生命周期 = "先密集迁移、后偶发" | 用户确认 | 每租户 onboarding 期是学习其模板的黄金窗口；**平台层导入永不停**，学习闭环不可冻结 |
| 后端当前**零 ML/LLM 依赖**（纯规则） | 核实 `requirements.txt` | 引入小模型 = 新增推理基建，触发条件要收紧（§5、§7） |
| 当前**无登录 / 无 user / 无 tenant 上下文**，全匿名（Q322） | `feature-clarifications.md`、`models/*` 全表无 tenant 字段 | **多租户根来源不存在**，本线强依赖 SaaS 主线先建根（§9.1） |

---

## 2. 决策依据（为什么不做这些——三方架构共识）

| 替代方案 | 裁定 | 理由 |
|---|---|---|
| LLM 端到端抽取（喂整篇→出结构） | ❌ 否决 | 非确定性 + 幻觉会改写/漏正文，违反保真不变量；多租户下"正文外发"在数据驻留上更不可接受；C001–C006 对账在 LLM 输出上无法保证 |
| pandoc / mammoth → HTML → 再解析 | ❌ 否决 | 有损转换丢掉 style sid / outlineLvl / bold ratio / vMerge —— 正是启发式赖以工作的信号，自废武功 |
| 重写解析器 | ❌ 否决 | 现有三阶段分层健康，保真原则守得好，无收益；§9.3 证实 parser 核心租户化**零改动** |
| 强制所有文档用标准 heading 样式 | ⚠️ 部分 | 私有化下有效；SaaS 下无法强制客户改模板，转而靠"每租户学习其模板"（主轴 B） |

**保留的地基**：三阶段（Normalizer→Structurer→Serializer）、保真不变量
（1 段落 ↔ 1 IR 块 ↔ 1 节点、内容 0 改写）、HIGH 自动 / MEDIUM 预标 / LOW 候选
+ 模式批量 + 样式记忆。

---

## 3. 已核实的 SaaS 硬伤（必须先堵，精确到代码）

1. **`tb_heading_style_rule.style_name` 是 `unique=True`，注释明写"全局单租户"**
   （`backend/app/models/heading_rule.py:22,27`）。
   → A 公司"章节标题"=L1 与 B 公司"章节标题"=L2 撞唯一约束。
   **改**：`tenant_id` 列 + 复合唯一 `(tenant_id, style_name)`。

2. **`heading_learning_service.reaggregate()` 跨所有 `procedure_id` 投票聚合**
   （`backend/app/services/heading_learning_service.py:55-123`）。
   → A 公司纠偏行为污染 B 公司规则，**串户事故**。
   **改**：投票口径加 `tenant_id` 过滤；`observe_node_edit` / `reaggregate` 透传租户。

3. **`heading_synonyms.yaml` 单一全局内置文件**，无"平台默认 + 租户覆盖"分层
   （`backend/app/parser/data/heading_synonyms.yaml`）。
   **改**：降级为平台默认底座 + 每租户覆盖表，解析时合并（租户优先）。

4. **（v2 新增）IDOR 越权横切**：`get_or_404` / `_get_node` 用 `db.get(Model, id)`
   **按 id 直取、不校验归属**（`heading_rule_service.py:49`、`numbering_profile_service.py:45`、
   `node_service.py:55`）。→ SaaS 下租户 A 拿 B 的 id 调 PUT/DELETE 即可改 B 的数据。
   **改**：所有按 id / procedure_id 的直取入口加 `tenant_id` 归属过滤（横切，远超三张表，见 §9.2）。

> 现在加一列 vs 将来迁全表 + 排查串户，成本差一个数量级。

---

## 4. 三条主轴

### 主轴 A —— 多租户隔离（新的第一性问题）
规则、学习事件、动态字典、同义词、上传临时 media、**以及越权边界**（§9.2）全部按租户隔离。
不可回退决策，越晚做越贵。

### 主轴 B —— 把学习闭环升格为护城河
- 每租户密集迁移期 = 学习其模板黄金窗口；纠偏后该租户后续文档自动 HIGH。
- "用得越多手工越少" 在 SaaS 里是**留存与复购理由**。
- **当下 ROI 最高的投入是复查面板吞吐 + 学习收敛速度**（模式批量、键盘流、
  样式记忆预热、迁移批次"一次配置多文档复用"），**不是 parser 精度**。

### 主轴 C —— 配置自助化，替代调参跑步机
> 平台侧正则只保留通用底座；**租户特例一律走"配置 + 学习"，绝不进
> `_classify_numbering_base` 主干、绝不为单客户发版。**

`NumberingProfile` / `numbering_overrides` 做成租户级配置 + UI 自助（CRUD 后端已存在，
`routers/heading_rules.py:70-108`）。新客户 = 一条配置，不是一个工单。

---

## 4.5 多租户 parser 精度模型（v2 新增 —— 核心理论）

### 4.5.1 没有"一个全局高精度 parser"

单租户 P=0.98 是把启发式过拟合到一个有限模板族换来的。多租户没有"一个模板族"。
**精度不是全局算法的属性，而是分层来源 + 每租户收敛的结果。**

### 4.5.2 四层架构：全局冻结底座 + 租户增量层

| 层 | 信号 | 它到底是什么 | 是模型吗 | 归属 |
|---|---|---|---|---|
| **L0 样式反查** | `styles.xml` heading 1/2/3 / outlineLvl / basedOn（`styles.py:classify_with_source`） | lxml 读 xml + 查表 | ❌ **确定性代码** | 全局、冻结、**对所有租户恒高精度（免费底座）** |
| **L1 租户样式映射** | 同义词覆盖 + 动态字典 | DB 规则表；`learned` 是**计数投票**（`Counter.most_common`），非神经网络 | ❌ 统计+字典 | 按租户 |
| **L2 租户编号 profile** | `N、`/`N.`/`一、` 算不算标题、几级 | 正则 + 配置表 | ❌ 规则/配置 | 按租户 |
| **L3 通用启发式** | 字号/加粗/短段/编号兜底 | 加权打分（`if font≥p85: score+=0.25`） | ❌ 手工规则 | 全局，**封顶 0.84 不自动入库** |
| **Phase 2（可选未来）** | text+font+bold+numbering→level | fastText/小分类器，中心化 | ✅ **唯一的模型，只补 L3 冷启动** | 平台 |

> **澄清（回应"L0 是我训的模型吗"）**：**不是。L0–L3 现在无一是模型。**
> L0 是 OOXML 标准自带的结构化信息读取，零训练零数据——它"对所有租户免费且恒定高精度"
> **恰恰因为它不是模型**（无泛化/漂移/训练成本）。唯一的模型是 Phase 2 那个只补冷启动、
> 不接管解析的中心化分类器。

**铁律**：L0/L3 全局层**只增不改**；租户特异性一律下沉 L1/L2 的配置与学习。
这条直接解决"调参跑步机"。

### 4.5.3 精度 KPI 改为"每租户收敛曲线"

衡量从"平均 P"改为 **"新租户从第 1 份到稳定态需几份纠偏"**（收敛步数）。
一个新租户的达成路径：

```
Onboarding（密集迁移期）：L0 自动标好 + 其余进复查面板（模式批量+键盘流），第一份多点几下
收敛（Day 1..N）：每次纠偏喂学习闭环 → 该租户 L1/L2 逐步固化；投票护栏（≥3 文档一致）防个例污染
稳定态：后续同模板文档趋近全自动（L0+L1+L2 命中）；L3+复查+保真校验永久兜底
```

### 4.5.4 稳定性：import 即快照（已有，补一道锁）

- **已有**：parse→import 两步，import 落持久 `ProcedureNode` 不重解析 → **学习只影响新文档，
  历史文档冻结**。避开了"展示时按需重解析导致历史漂移"的审计灾难。
- **补**：草稿态（parse 了未 import）中途规则变会漂移。建议 parse 时把 `rule_revision`
  快照进草稿，import 校验（`heading_rule` 已有 `revision` 字段，成本极低）。

---

## 5. 红线（必须焊死的约束）

1. **保真不变量不松动**：parser 不切分/合并段落、不改写内容。
2. **LLM/模型只判 heading，永不碰内容序列化**。
3. **模型/数据不跨租户泄露**：若 Phase 2 训共享分类器，只用脱敏/聚合特征，
   原文不出租户边界，且写进客户协议。
4. **不为单客户改主干正则、不为单客户发版**——特例走配置/学习。
5. **（v2）任何按 id/procedure_id 的读写入口必须带租户归属校验**（防 IDOR，§9.2）。

---

## 6. 任务清单

### 前置依赖（SaaS 主线，本线不自建）

| ID | 任务 | 说明 |
|---|---|---|
| **DEP-0** | 租户根 + 请求级 tenant 上下文 | `Procedure` 等业务表加 `tenant_id`；鉴权/中间件把 tenant 注入请求（FastAPI dependency）。**P0-1/P0-2 的 `tenant_id` 来源即此**。本线只消费，不建根 |

### Phase 0 —— 解析线租户化（依赖 DEP-0；DEP-0 未就绪时先做 §9.5 的"留缝"子集）

| ID | 任务 | 验收标准 | 性质 |
|---|---|---|---|
| P0-1 | 三表租户化迁移：`tb_heading_style_rule` 加 `tenant_id` + 复合唯一 `(tenant_id, style_name)`；`tb_heading_learning_event` 加 `tenant_id` + 复合索引；`tb_numbering_profile` 加 `tenant_id` + 复合唯一。Alembic 迁移含回填默认租户。**注意 SQLite（测试）改约束需重建表**。 | 迁移可 upgrade/downgrade；现有数据回填默认 tenant；复合唯一生效 | 新迁移 |
| P0-2 | 聚合器 + 注入按租户分区：`reaggregate(db, name)`→`(db, name, tenant_id)` 投票查询加过滤；`observe_node_edit` 透传租户；`active_style_overrides(db)`/`active_numbering_overrides(db)` 加 `tenant_id` 参数；`node_service._learn_from_edit` 解析出 tenant（node→procedure→tenant 或 node 冗余 tenant_id，见 §9.4）；`parse_service.parse` 接 tenant 并传入注入。 | 新增单测：两租户同名样式互不投票、互不覆盖 | 服务改造 |
| P0-2.5 | **（v2）IDOR 越权修复**：`heading_rule_service.get_or_404`、`numbering_profile_service.get_or_404`、`node_service._get_node` 及 `get_nodes/batch_update/reorder` 的按 id/procedure_id 直取，全部加 `tenant_id` 归属过滤。 | 单测：跨租户 id 访问返回 404，不泄露/不修改 | 安全横切 |
| P0-3 | 同义词分层：`heading_synonyms.yaml` 作平台默认 + 每租户覆盖表，解析时合并（租户优先）。 | 单测：同名样式在不同租户解析出不同 level | 解析衔接 |
| P0-4 | `ResolverChain` 重构：Tier2 启发式封装成 `[StyleResolver, SynonymResolver, OutlineResolver, HeuristicResolver]`，对外 API 不变。 | 现有 66 个 parser 单测 0 退化 | 纯内部重构 |
| P0-5 | `NumberingProfile`（解析侧）：把散落 `_RE_*` 收进 profile 对象，预留 `load_profile_for(tenant)` 入口。 | 现有解析行为逐字节不变 | 纯内部重构 |
| P0-6 | 复查 UI 吞吐打磨（前端）：模式批量分组勾选、键盘流、样式记忆预热。 | 迁移一份零样式文档操作次数较基线下降并截图佐证 | 前端 |

> 优先级：DEP-0 →（P0-1 → P0-2 → P0-2.5）→ P0-3；P0-4/P0-5/P0-6 可并行、不依赖 DEP-0。

### Phase 1 —— SaaS MVP

- 全链路租户隔离落地；每租户动态字典/同义词覆盖在 UI 可维护。
- 导入做成 **onboarding 向导**；编号体例**配置自助 UI**（主轴 C）。
- 前端**平台/租户视角分化**（§8）。

### Phase 2 —— 规模化（触发才做，勿提前）

- **触发条件**：正则维护成本超线，或上线首个**非中文 / 非 SOP** 客户。
- 用 `tb_heading_learning_event`（已 append-only 采集全体租户纠偏 = 天然标注集）
  训**中心化** heading 四分类器，替 `HeuristicResolver`（复用 P0-4 插槽）。
- 守 §5 全部红线；只补 L3 冷启动，**不接管 L0/L1/L2**。

---

## 7. 杠杆判断速查（SaaS 下的 ROI 重算）

| 杠杆 | 私有化单租户 | SaaS 多租户 |
|---|---|---|
| 导入=遗留迁移、冻结 parser | 成立，搬完即冻 | **单租户**成立；**平台层**导入永不停，学习闭环不可冻结 |
| 配置化替代调参（主轴 C） | 可选 | **刚需**（模板无界） |
| 小模型替编号字典（Phase 2） | 排除（基建成本 > 收益） | **中长期 ROI 转正**（维护成本爆炸 + 学习事件即训练集 + 基建被全租户摊薄），但需满足触发条件与红线 |

---

## 8. 前端平台/租户边界（v2 新增 —— 回应"前端是否需变化以区分我和租户"）

**需要，但不是从零建**：现有 `frontend/src/views/settings/HeadingRulesView.vue` +
`api/headingRules.ts` 已是规则管理界面，但它现在是"全局单租户"——**把"平台默认"和
"租户规则"混为一谈**。SaaS 下前端要回答三条边界：

1. **作用域 scope**：每条规则/profile 属于"平台默认"还是"本租户"。现有界面加 scope 维度。
2. **来源标识 provenance**（低成本、高体验价值）：可视化 `heading_rule.source`：
   - `platform-default`（平台给，租户**只读、不可删，只能覆盖**）
   - `manual`（本租户钉死的"记住此样式"）
   - `learned`（本租户**自动学到的** —— 这个标签本身就是护城河的体验化）
   > 前端 `HeadingRule` interface 已有 `source` 字段（`headingRules.ts`），**缺 `scope`**，需补。
3. **可见性/权限**：租户**只见自己 + 平台默认（只读）**，绝不见别的租户；
   平台运营方有跨租户视图但**默认不看租户文档内容**（数据治理）。

两类前端面：

| 面 | 给谁 | 怎么来 |
|---|---|---|
| **租户自助面** | 租户管理员 | **扩展现有** `HeadingRulesView`：加 scope + provenance + "记住此样式"；`numbering-profiles` 做成"我用 `N、` 做 L1"友好配置；复查面板数据按租户隔离 |
| **平台运营面** | 你 / 超管 | **全新**：平台默认底座维护、跨租户健康看板（每租户**收敛曲线 KPI**、谁冷启动卡住）、(Phase 2) 模型治理 |

**与 Phase 对应（避免过度设计）**：Phase 0 前端基本不动（P0-6 + 可顺手加的 provenance
标识）；真正的视角分化在 **Phase 1**。可选 nice-to-have：复查面板 HIGH 绿色细分
"L0 标准样式（全局）" vs "L1 你公司教会的（租户）"，强化"为我学习"感知。

---

## 9. 依赖变动与影响边界评估（v2 新增 —— 本轮核心）

### 9.1 决定性结论：tenant_id 根来源当前不存在

`grep tenant|org_id|organization|workspace|company_id` 在 `backend/app/models/*` **0 命中**；
`Procedure`（`models/procedure.py`）、`ProcedureNode`、`Folder` 等**全部无租户维度**；
系统**无登录、无 user、无 tenant 上下文**（Q322）。

→ **"给 heading_rule 加 tenant_id"不是孤立动作，是"全系统多租户化"的子集。**
本线**强依赖 DEP-0**（租户根 + 请求级 tenant 上下文）。在 DEP-0 就绪前，本线能独立做的
只有 §9.5 的"留缝"重构（签名预留 tenant 形参、归属校验骨架），真正接线要等根。

### 9.2 横切风险：IDOR 越权（远超三张表）

所有"按 id / procedure_id 直取、不校验归属"的入口，在 SaaS 下都是越权点：

| 位置 | 现状 | 风险 |
|---|---|---|
| `heading_rule_service.get_or_404:49` | `db.get(HeadingStyleRule, id)` | 跨租户改/删规则 |
| `numbering_profile_service.get_or_404:45` | `db.get(NumberingProfile, id)` | 跨租户改/删编号体例 |
| `node_service._get_node:55` / `get_nodes:66` / `batch_update:186` / `reorder:222` | 按 id/procedure_id 直取 | 跨租户读/改节点正文 |

→ 租户化时必须**同步**加 `tenant_id` 过滤（P0-2.5）。这是安全级，不可延后。

### 9.3 影响矩阵（文件 → 符号 → 改动 → 依赖）

| 层 | 单元 | 改动 | 备注 |
|---|---|---|---|
| **model** | `heading_rule.py` | +`tenant_id`，`unique(style_name)`→`(tenant_id, style_name)` | 去掉"全局单租户"注释 |
| | `heading_learning_event.py` | +`tenant_id` + 复合索引 | 投票分区基础 |
| | `numbering_profile.py` | +`tenant_id` + 复合唯一 | 同 heading_rule |
| | `node.py` | **建议** +`tenant_id` 冗余 | 见 §9.4 |
| **service** | `heading_rule_service` | `active_style_overrides`/`list_rules`/`get_or_404`/`_find_by_name`/`create` 全加 tenant | `get_or_404` 同时修越权 |
| | `numbering_profile_service` | 同上对称 | |
| | `heading_learning_service` | `observe_node_edit`/`reaggregate(+tenant)`/`_append` 存 tenant；投票 query 加过滤 | §3.2 核心 |
| | `node_service` | `_learn_from_edit` 解析 tenant；`_get_node`/`get_nodes`/`batch_update`/`reorder` 加归属校验 | 越权横切 |
| | `parse_service.parse` | 入参 +tenant，注入调用传 tenant | 来源 = 请求上下文 |
| | `import_service.import_procedure` | 落 `ProcedureNode` 带 tenant | |
| **router** | `heading_rules.py`、`parse.py` 等 | 从 tenant 上下文 dep 取租户 | 依赖 DEP-0 |
| **schema** | `HeadingRuleCreate/Update`、`NumberingProfile*` | **不接受** tenant_id（防伪造，从上下文注入）；`*Out` +`scope` | 前端 provenance |
| **parser core** | `parse_docx`/`classify_with_source`/`heading_detector` | **零改动**（纯函数，接受注入 dict） | ✅ 分层红利 |
| **同义词** | `parser/data/heading_synonyms.yaml` + `synonyms.py` | 平台默认 + 租户覆盖合并加载 | P0-3 |
| **前端** | `api/headingRules.ts`、`HeadingRulesView.vue`、复查面板 | API 签名基本不变（tenant 走 token/header）；view 加 scope/provenance；数据按租户 | §8 |
| **测试** | `test_heading_rule_service`、`test_numbering_profile_service`、`test_heading_learning_service`、`test_parse_service`、`test_import_service` | 全部更新调用签名（+tenant）；新增跨租户隔离/越权用例 | 6+ 文件 |

### 9.4 设计抉择：node 等表是否冗余 tenant_id

**建议冗余**（不只 join procedure 取）。理由：① 行级隔离查询可直接带 `WHERE tenant_id=?`，
不必每次 join；② 学习触发点 `_learn_from_edit` 要 tenant，node 自带省一次查询；
③ 与多租户"每表都能独立按租户过滤"的通行实践一致。代价：写入时回填 + 与 procedure 一致性
（同事务写入即可保证）。

### 9.5 修正后的依赖顺序 + 可独立先做的子集

```
DEP-0（SaaS 主线：租户根 + tenant 上下文）
   └─ P0-1（三表迁移）→ P0-2（聚合/注入分区）→ P0-2.5（越权修复）→ P0-3（同义词分层）
P0-4 / P0-5 / P0-6  ← 不依赖 DEP-0，可即刻并行
```

**DEP-0 未就绪时可独立先做的"留缝"重构**（零行为变化、为接线铺路）：
- service 函数签名预留 `tenant_id: str | None = None`（默认 None = 当前单租户/平台默认）；
- `get_or_404` 改造成"带可选归属校验"的形态（None 时退化为现状）；
- P0-4/P0-5 纯内部重构本就独立。
这样 DEP-0 落地后，只需把 None 换成真实 tenant，不再大动。

---

## 10. 参考

- [`docs/word-parser-solution.md`](../../word-parser-solution.md) —— 解析方案 A + C
- [`docs/parser-comprehensive-evaluation.md`](../../parser-comprehensive-evaluation.md) —— 综合评估与 L0–L3 重构建议
- 学习闭环：`backend/app/services/heading_learning_service.py`、`node_service.py:31-39,140,217`、
  `backend/app/models/heading_rule.py`、`heading_learning_event.py`
- 注入点：`backend/app/services/parse_service.py:48-50`、`backend/app/parser/styles.py:98-140`
- 规则 CRUD：`backend/app/routers/heading_rules.py`、`services/heading_rule_service.py`、
  `services/numbering_profile_service.py`
- 前端：`frontend/src/api/headingRules.ts`、`frontend/src/views/settings/HeadingRulesView.vue`
