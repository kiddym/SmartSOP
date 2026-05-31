# Word 解析与标注 —— SaaS 多租户演进方案（执行 plan）

> **日期**：2026-05-31
> **状态**：待执行（交接给"正在做 SaaS 化"的 agent）
> **载体**：本文档自包含，无需本对话上下文即可冷启动执行。
> **前置上游**：本 plan 只覆盖**解析器 / 标注 / 动态字典**这条线在 SaaS 下的改造，
> 假设通用租户上下文（tenant 中间件 / 鉴权 / 路由）由 SaaS 主线另行提供；本文标注衔接点。

---

## 0. TL;DR

系统未来要做成 **SaaS：多租户、每家公司有自己的 Word 模板**。这把工程主轴从
"解析得多准"换成 **"每个租户多快学会他的模板、且彼此绝不串户"**。

- **不重写解析器、不上 LLM 端到端、不引 pandoc/mammoth**（理由见 §2）。
- 现有的"纠偏→投票→动态字典"学习闭环（M1–M4b）是 SaaS 最值钱的护城河，
  但它现在是**单租户**的，且有两处会在 SaaS 下**串户/撞约束**的硬伤（§3）。
- **Phase 0（现在就做，低成本不可回退）**：给三类数据加 `tenant_id`、改复合唯一、
  投票按租户分区、同义词分层；并把 Tier2 启发式重构成可替换的 `ResolverChain`、
  把散落正则收进 `NumberingProfile`。详见 §6 任务清单。

---

## 1. 不可回退的事实（决定方案走向）

| 事实 | 来源 | 影响 |
|---|---|---|
| 未来做 SaaS，多租户 | 用户确认（2026-05-31） | 数据/规则/学习必须按租户隔离 |
| 每家公司有**自己的 Word 模板** | 用户确认 | 模板随客户**无界增长**，调参跑步机从风险变必然 |
| 单租户导入生命周期 = "先密集迁移、后偶发" | 用户确认 | 每租户 onboarding 期是学习其模板的黄金窗口；**平台层导入永不停**（新租户持续进场），故学习闭环必须常驻、不可冻结 |
| 后端当前**零 ML/LLM 依赖**（纯规则） | 核实 `requirements.txt` | 引入小模型 = 新增推理基建，非"顺手复用"，触发条件要收紧（§5） |
| 当前设计是"受控内网、单组织、反过度工程" | `docs/feature-clarifications.md` Q322 | SaaS 化会突破此前提；任何新基建要乘"违背极简 DNA"的惩罚系数 |

---

## 2. 决策依据（为什么不做这些——三方架构共识）

| 替代方案 | 裁定 | 理由 |
|---|---|---|
| LLM 端到端抽取（喂整篇→出结构） | ❌ 否决 | 非确定性 + 幻觉会改写/漏正文，违反保真不变量；多租户下"正文外发"在数据驻留上更不可接受；C001–C006 对账在 LLM 输出上无法保证 |
| pandoc / mammoth → HTML → 再解析 | ❌ 否决 | 有损转换丢掉 style sid / outlineLvl / bold ratio / vMerge —— 正是启发式赖以工作的信号，自废武功 |
| 重写解析器 | ❌ 否决 | 现有三阶段分层健康，保真原则守得好，无收益 |
| 强制所有文档用标准 heading 样式 | ⚠️ 部分 | 私有化下有效；SaaS 下无法强制客户改模板，转而靠"每租户学习其模板"（主轴 B） |

**保留的地基**：三阶段（Normalizer→Structurer→Serializer）、保真不变量
（1 段落 ↔ 1 IR 块 ↔ 1 节点、内容 0 改写）、HIGH 自动 / MEDIUM 预标 / LOW 候选
+ 模式批量 + 样式记忆。

参考：[`docs/word-parser-solution.md`](../../word-parser-solution.md)、
[`docs/parser-comprehensive-evaluation.md`](../../parser-comprehensive-evaluation.md)。

---

## 3. 已核实的 SaaS 硬伤（必须先堵，精确到代码）

1. **`tb_heading_style_rule.style_name` 是 `unique=True`，注释明写"全局单租户"**
   （`backend/app/models/heading_rule.py:22,27`）。
   → A 公司"章节标题"=L1 与 B 公司"章节标题"=L2 撞唯一约束。
   **改**：`tenant_id` 列 + 复合唯一 `(tenant_id, style_name)`。

2. **`heading_learning_service.reaggregate()` 跨所有 `procedure_id` 投票聚合**
   （`backend/app/services/heading_learning_service.py:55-123`）。
   → A 公司纠偏行为污染 B 公司规则，**串户事故**。
   **改**：投票口径加 `tenant_id` 过滤；`observe_node_edit` 透传租户。

3. **`heading_synonyms.yaml` 单一全局内置文件**，无"平台默认 + 租户覆盖"分层
   （`backend/app/parser/data/heading_synonyms.yaml`）。
   **改**：降级为平台默认底座 + 每租户覆盖表，解析时合并（租户优先）。

> 现在加一列 vs 将来迁全表 + 排查串户，成本差一个数量级。即便 SaaS 推迟，
> 留 `tenant_id` 与分层同义词在私有化下零害处。

---

## 4. 三条主轴

### 主轴 A —— 多租户隔离（新的第一性问题）
规则、学习事件、动态字典、同义词、上传临时 media 全部按租户隔离。
不可回退决策，越晚做越贵。

### 主轴 B —— 把学习闭环升格为护城河
- 每租户密集迁移期 = 学习其模板黄金窗口；纠偏后该租户后续文档自动 HIGH。
- "用得越多手工越少" 在 SaaS 里是**留存与复购理由**。
- **当下 ROI 最高的投入是复查面板吞吐 + 学习收敛速度**（模式批量、键盘流、
  样式记忆预热、迁移批次"一次配置多文档复用"），**不是 parser 精度**。

### 主轴 C —— 配置自助化，替代调参跑步机
> 平台侧正则只保留通用底座；**租户特例一律走"配置 + 学习"，绝不进
> `_classify_numbering_base` 主干、绝不为单客户发版。**

`NumberingProfile` / `numbering_overrides` 做成租户级配置 + UI 自助：
客户自己声明"我用 `N、` 做 L1"，或在复查面板纠偏几次让系统学。
新客户 = 一条配置，不是一个工单。

---

## 5. 红线（必须焊死的约束）

1. **保真不变量不松动**：parser 不切分/合并段落、不改写内容。
2. **LLM/模型只判 heading，永不碰内容序列化**。
3. **模型/数据不跨租户泄露**：若 Phase 2 训共享分类器，只用脱敏/聚合特征，
   原文不出租户边界，且写进客户协议。
4. **不为单客户改主干正则、不为单客户发版**——特例走配置/学习。

---

## 6. 任务清单

### Phase 0 —— 现在就做（内网即可落地，为 SaaS 留口子；低成本不可回退）

| ID | 任务 | 验收标准 | 性质 |
|---|---|---|---|
| P0-1 | 三类数据租户化迁移：`tb_heading_style_rule` 加 `tenant_id` + 复合唯一 `(tenant_id, style_name)`；`tb_heading_learning_event` 加 `tenant_id` + 复合索引；动态字典/同义词覆盖表加 `tenant_id`。Alembic 迁移含回填默认租户。 | 迁移可 upgrade/downgrade；现有单租户数据回填到默认 tenant；唯一约束生效 | 新迁移 |
| P0-2 | 聚合器租户化：`reaggregate` 投票按 `tenant_id` 分区；`observe_node_edit` 透传租户。 | 新增单测：两租户同名样式互不投票、互不覆盖 | 服务改造 |
| P0-3 | 同义词分层：`heading_synonyms.yaml` 作平台默认 + 每租户覆盖表，解析时合并（租户优先）。 | 单测：同名样式在不同租户解析出不同 level | 解析衔接 |
| P0-4 | `ResolverChain` 重构：把 Tier2 启发式封装成 `[StyleResolver, SynonymResolver, OutlineResolver, HeuristicResolver]` 链，每个返回 `(level, conf, src)` 或 None。**对外 API 不变**。 | 现有 66 个 parser 单测 0 退化；启发式逻辑等价 | 纯内部重构 |
| P0-5 | `NumberingProfile`：把散落的 `_RE_*` 编号正则收进一个 profile 对象，预留 `load_profile_for(tenant)` 入口。 | 现有解析行为逐字节不变；profile 可被租户配置覆盖（接口预留即可） | 纯内部重构 |
| P0-6 | 复查 UI 吞吐打磨（前端）：模式批量分组勾选、键盘流、样式记忆预热。 | 迁移一份零样式文档的人工操作次数较基线下降并截图佐证 | 前端 |

> P0-4 / P0-5 是纯内部重构、不改对外契约、单测保活，是 Phase 2 小模型的插槽地基，
> 即便不上模型也独立有益。优先级：P0-1 > P0-2 > P0-3 >（P0-4、P0-5、P0-6 可并行）。

### Phase 1 —— SaaS MVP（决定做 SaaS 后）

- 全链路租户隔离（衔接 SaaS 主线的 tenant 中间件）。
- 每租户动态字典 / 同义词覆盖在 UI 可维护。
- 导入做成 **onboarding 向导**（对应"密集迁移期"）。
- 编号体例**配置自助 UI**（主轴 C 落地）。

### Phase 2 —— 规模化（触发才做，勿提前）

- **触发条件**：正则维护成本超线，或上线首个**非中文 / 非 SOP** 客户。
- 用沉淀的 `tb_heading_learning_event`（已 append-only 采集全体租户纠偏 = 天然标注集）
  训一个**中心化** heading 四分类器（text+font+bold+numbering → level/content），
  替掉 `HeuristicResolver`（复用 P0-4 插槽）。
- **守 §5 全部红线**：只判 heading、不碰内容；脱敏特征、原文不跨租户；
  平台统一一个推理服务，不是每租户一个。
- 在触发前，主轴 C 的配置化 + 学习闭环够用——**别提前上，违背极简 DNA**。

---

## 7. 杠杆判断速查（SaaS 下的 ROI 重算）

| 杠杆 | 私有化单租户 | SaaS 多租户 |
|---|---|---|
| 导入=遗留迁移、冻结 parser | 成立，搬完即冻 | **单租户**成立；**平台层**导入永不停，学习闭环不可冻结 |
| 配置化替代调参（主轴 C） | 可选 | **刚需**（模板无界） |
| 小模型替编号字典（Phase 2） | 排除（基建成本 > 收益） | **中长期 ROI 转正**（维护成本爆炸 + 学习事件即训练集 + 基建被全租户摊薄），但需满足触发条件与红线 |

---

## 8. 参考

- [`docs/word-parser-solution.md`](../../word-parser-solution.md) —— 解析方案 A + C
- [`docs/parser-comprehensive-evaluation.md`](../../parser-comprehensive-evaluation.md) —— 综合评估与 L0–L3 重构建议
- 当前学习闭环：`backend/app/services/heading_learning_service.py`、
  `backend/app/models/heading_rule.py`、`backend/app/models/heading_learning_event.py`
- 解析核心：`backend/app/parser/heading_detector.py`、`structurer.py`、`styles.py`
