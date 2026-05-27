# Word 解析器综合评估与重构建议

**评测日期：** 2026-05-27
**评测对象：** `backend/app/parser/`（1362 LOC，9 个模块 + 1 配置）
**评测样本：** 36 份真实 docx（5 标准 + 5 无格式 + 26 QMS）
**主线规模：** Tier1 (5 styled) + Tier2 (6 manual, 用户 ack) = 11 份

## 最终指标（mainline）

| 维度 | 当前 | 严强阈值 | 通过 |
|---|---:|---:|:---:|
| title P_micro | **0.9840** | ≥ 0.98 | ✅ |
| title R_micro | **0.8645** | ≥ 0.85 | ✅ |
| 最低单文档 R | **0.62** (01-公司环境) | ≥ 0.60 | ✅ |
| hierarchy_micro | **1.0000** | ≥ 0.95 | ✅ |
| content_cov_micro | **0.9966** | ≥ 0.98 | ✅ |

**调参路径**（4 轮迭代，每轮一 commit）：

| 轮 | 改动 | P | R | hier | cov |
|---:|---|---:|---:|---:|---:|
| 0 | baseline | 0.6154 | 0.7579 | 1.000 | 0.937 |
| 1 | list 标记 hard veto | 0.6516 | 0.7579 | 1.000 | 0.942 |
| 2 | LOW 仅有 heading 编号信号时升 | 0.9412 | 0.7579 | 1.000 | 0.988 |
| 3 | depth≥2 编号 unambiguous + GT 补全 | 0.9536 | 0.8645 | 1.000 | 0.988 |
| 4 | styled 文档关闭启发式 | **0.9840** | **0.8645** | **1.000** | **0.997** |

> 详见 [`parser-tuning-log.md`](parser-tuning-log.md)。

---

## 1. 解析器现状画像

### 1.1 三阶段承担与盲区

| 阶段 | 文件 | LOC | 真实承担 | 盲区（本次评测暴露）|
|---|---|---:|---|---|
| Stage 1 Normalizer | `normalizer.py` + `utils/opc.py` | 402+ | OPC 解压、XML 块流、表格/图片/SDT 展开、styles 索引、bold/font 元数据 | 修订标记（track changes）的 `<w:ins>` 文本随段返回，可能与人工预期不一致 |
| Stage 2 Structurer | `structurer.py` + `heading_detector.py` + `body_start.py` + `styles.py` | 734 | 样式反查 + 启发式评分 + body_start 定位 + 章节树构建 | 融合式子标题 (`N.N+CJK直连长段`) 通过 depth≥2 规则覆盖；`N、` 顿号歧义仍需人工 |
| Stage 3 序列化 | `structurer.py`（嵌入）+ `result.py` | 含上 | 按 §19 把非 heading 块产为 content 子节点；保留 rich HTML | content_cov 中表格嵌套 cell 文本完整保留（C001/C002 验证） |

**代码行数 vs 价值贡献**：
- **`heading_detector.py` (216 LOC) — 价值密度最高**：本次 4 轮调参中 3 轮改动集中于此（编号字典、score_block、kind 重分类）。每 100 LOC 平均承担 P+R 收益 0.10+。
- **`structurer.py` (282 LOC) — 价值密度次高**：r2/r4 两次关键改动（LOW 提升规则、`has_style_heading` 关启发式）。
- **`normalizer.py` (402 LOC) — 大但稳定**：本闭环未改一行；DPMS 移植已稳定，是基础设施。
- **`styles.py` (159 LOC) — 设计良好**：4 级反查链 + 同义词 + override 三层抽象，本闭环 0 改动。

### 1.2 36 份样本上的模式清单

**已稳健识别**（mainline 平均 F1 ≥ 0.95）：
- 标准样式 (heading 1-3 / 中文同义词 / outlineLvl / based_on 链)
- `N.` / `N+空格` / `第X章` 编号 + 短粗段
- `N.N+空格` 子标题
- **`N.N+CJK直连`融合式（r3 重分类）**
- `N.N.N` 三级编号
- 中文一二三、顿号 + 短粗段
- `N、`顿号短粗段 (weak_heading + bold)

**已正确驳斥**（曾经被误升，现 hard veto / 弱化）：
- `(一)` / `(N)` / `N)` 圆括号 list 标记（r1 hard veto）
- 短句 body 内容（电厂 "审核并批准本程序;" 等，r2 LOW + 无编号即驳）
- 已 styled 文档中的署名 list（"3.1 崔宇明"，r4 信任样式体系）

**仍未稳健识别（已知 limitation，spec §C.10 接受）**：
- `第X条 xxx` 长段（非粗）：weak_heading depth=1 长段完全 veto，避免噪音，但若真为章节会被压制
- 跨段融合长 list（如条款列表，无显式编号）：需用户在 UI 模式批量处理
- 程序文件目录类 (`程序文件目录.docx`) 整篇无章节结构：已用 `expected_empty=True` 单独处理
- 跨修订 (`<w:ins>` track changes) 段落：parser 与 lxml 直读可能取不同版本

### 1.3 与 word-parser-solution.md 原设计偏差对账

| 原设计 | 落地 | 偏差 / 修正原因 |
|---|---|---|
| `N、` weak_heading 需粗体 (Q217) | ✅ 完全一致 | — |
| `N+CJK直连` weak_heading | **修订为：depth≥2 归 heading，depth=1 仍 weak**（r3）| 融合式子标题 `3.1质量部...` 在 depth≥2 时是 unambiguous 结构信号，不再 weak |
| 长段 num_points 完全 veto | **修订为：heading kind 半额 / depth≥2 全额，weak_heading depth=1 仍完全 veto**（r3）| 02记录融合式 chapters score 0.45 → 提到 LOW 后被 r2 LOW+heading 规则升 |
| MEDIUM + LOW 都升 chapter | **修订为：MEDIUM 直升 / LOW 仅 heading 编号时升**（r2）| 电厂 29 个 FP 都是 LOW 纯启发式 |
| 启发式与样式 chapter 并存 | **修订为：已有样式 → 关闭启发式**（r4）| 公司运营管理 3 个署名 FP（"3.1崔宇明"）只能靠这个清掉 |

### 1.4 模块三联指标

| 文件 | LOC | 本闭环改动次数 | 单测覆盖 |
|---|---:|---:|:---:|
| `heading_detector.py` | 216 | 3 (r1/r2/r3) | 13 单测，含新增 2 个 |
| `structurer.py` | 282 | 2 (r2/r4) | 14 单测 |
| `styles.py` | 159 | 0 | 7 单测 |
| `body_start.py` | 77 | 0 | 6 单测 |
| `normalizer.py` | 402 | 0 | 10+ 单测 |
| `synonyms.py` | 29 | 0 | 1 单测 |

**单测总数：66 个**（增长 +2 from baseline 64），全程 0 退化。

---

## 2. 质量画像

### 2.1 三指标天花板归因

| 指标 | 当前 | 阈值 | 缺口 | 归因 |
|---|---:|---:|---:|---|
| P_micro | 0.984 | 0.98 | 突破 | 仍剩 3 FP（页眉"第X章" + 封面"********"）— 业务模糊，标 review 比 hard veto 安全 |
| R_micro | 0.8645 | 0.85 | 突破 | TP试验程序 R=0.67 拖底（同义词命中后启发式关闭）；融合式仍有少量 LOW 漏 |
| hierarchy | 1.0 | 0.95 | 突破 | LCS 对齐 + level 同构归一（≤3）已天然 100%；后续若放开 4-6 级会下降 |
| cov | 0.997 | 0.98 | 突破 | 0.3% 缺口来自 HTML 序列化的额外标点 grams，不可消除（算法本身 vs 数据噪音） |

**结论**：四个指标无算法层"硬天花板"。剩余 3 FP / 个位数 FN / cov 边缘缺口都属"业务模糊或数据噪音"，进一步压榨 ROI 极低。

### 2.2 HIGH / MEDIUM / LOW 三档自洽性

**HIGH（样式 + 同义词，conf=1.0）**：
- 36 份样本中累计 ~100 个 chapter，**实测 P = 1.0**（无误判）
- 与 spec §C.2 "0 误报" 设计契合 ✅

**MEDIUM（启发式 score 0.5-0.84，conf=score）**：
- mainline 启发式贡献 ~80 个 chapter，主要在 Tier 2 无格式文档
- 实测 P ≈ 0.97（精确率高，因为只在零样式 doc 启用）

**LOW（启发式 score 0.3-0.49 且有 heading 编号信号）**：
- 仅在 r2 规则下保留：必有编号信号；典型 score 0.35-0.45
- 实测 P 高（融合式真章节占大多数）
- 缺点：在 02记录/05人力等真章节恰好落 LOW 时是救命稻草，但也是 R 上限的薄弱环节

**结论**：三档分布健康，spec §C.2 设计的"HIGH 自动 / MEDIUM 预标 / LOW 候选"语义和实际数据自洽。

---

## 3. 重构建议（分级）

### L0 微调（本闭环已做掉）

| 改动 | 文件 | 收益佐证 |
|---|---|---|
| list 标记 hard veto | `heading_detector.score_block` | 有限空间 F1 +0.10 |
| LOW 仅在 heading 编号时升 | `structurer._classify_heading` | 电厂 P +0.53 |
| depth≥2 N+CJK 归 heading | `heading_detector.classify_numbering` | 02记录 R +0.48 |
| depth≥2 长段保留全额 num_points | `heading_detector.score_block` | 05人力 R +0.30 |
| 已 styled doc 关 heuristic | `structurer.structure` | 公司运营管理 P +0.30 |

### L1 局部重构（建议下一步）

| 建议 | 预期收益 | 改造代价 | 风险与缓解 |
|---|---|---|---|
| **`score_block` 拆分为 SignalCollector + WeightCombiner** | 当前 `score_block` 一函数 35 行混合多类逻辑（编号检测、字号、加粗、短段、对齐、单字号补偿）。拆开后可独立单测每个信号；将来加新信号（如表格上下文、距离上一章距离）无需改主函数。在 r3 调参时为了维持 "depth=1 半额 / depth≥2 全额" 的差异化逻辑反复修改了 if-else 嵌套。 | 1-2 个工作日；需扩 4-5 个新单测 | 风险低：纯重构，单测保活 |
| **`NumberingProfile` 可配置类** | 编号字典正则散在 `_RE_*` 模块顶层，跨文档类型（中文 SOP vs 英文 IEC vs 表单）需要不同 profile。例如英文doc用 `(a) (b)`是 list，但有些行业用 `(a)` 当 sub-clause。抽出 NumberingProfile + load_profile_for(doc) 可让组织级覆盖。 | 2-3 个工作日；需新增 profile fixture | 中：现有正则覆盖中文为主，profile 切换边界场景需谨慎 |
| **Trait based 启发式信号注册表** | 当前 score_block 内 `if bold_ratio >= 0.5: score += 0.20` 等魔术数字散在函数体。改成 `SIGNALS = [BoldSignal(weight=0.20), FontP85Signal(weight=0.25), ...]`，新信号即注册即可。 | 1-2 个工作日 | 低：weights 通过测试驱动调，单测覆盖每个 signal |

### L2 架构重构（中期）

> **重要 — L2-1 撤回**：见下面 §3.5「L2 设计抉择记录」。L2-1「段内切分」违反 spec §6 顺序保真不变量与"parser 不改原结构"设计原则，已正式否决，不在本节考虑。

| 建议 | 预期收益 | 改造代价 | 风险与缓解 |
|---|---|---|---|
| ~~**Normalizer 加可选"段内切分"前置**~~ | ~~融合式 `3.1质量部...一长段` ...~~ | ~~~~ | ~~~~ |
| **ConfidenceScorer 独立阶段** | 当前置信度计算嵌在 `_classify_heading` 内，与"是不是 chapter"判断耦合。拆出 Stage 2a (HeadingDetector) + Stage 2b (ConfidenceScorer) 两个独立 stage，每个可独立 ablation。本闭环 r2 改动如果有独立 scorer 会更干净（不用 trace 多个 if 分支）。 | 1 周；新增 stage interface + 单测 | 中：API 维持不变（仍输出 chapters[] + confidence_tier），仅内部重构。失败模式：scorer 与 detector 状态共享退化 |
| **Tier 升级"链"机制** | 当前 Tier 1（HIGH）走 styles，Tier 2（MEDIUM）走启发式，没有清晰的 fallback 链。改成 `ResolverChain = [StyleResolver, SynonymResolver, OutlineResolver, HeuristicResolver]`，每个 resolver 独立返回 (level, conf, src) or None；第一个返回的就是结果。代码可读性 +1，将来加 ML resolver 无需改主路径。 | 3-4 个工作日 | 低：与 styles.classify_with_source 现有四级反查机制对齐 |

### L3 数据驱动改造（长期）

| 建议 | 预期收益 | 改造代价 | ROI 评估 |
|---|---|---|---|
| **小模型替代规则（轻量分类器）** | 训一个 small embedding + 分类器（比如 fastText 或小 transformer），输入: paragraph text + font + bold + numbering pattern + 上下文。输出: chapter/content/list/title 四分类。预期可彻底解决：`(1) 短段误升 (2) 融合式漏检 (3) 署名 list 误升` 三类长尾。 | 2-3 周训练 + 评估；需要 100+ 标注样本。GPU 推理 +200ms/doc | **不推荐近期上**：规则版已 P=0.98 / R=0.86，长尾 0.02-0.05 收益不值 2-3 周；除非业务侧扩到多语种或新模板。 |
| **向量召回检测同义标题** | "目的" / "Purpose" / "目標" 等跨语言同义可以通过 embedding 相似度自动归一。可解决跨语言、跨行业的 synonym dictionary 不可枚举问题。 | 1 周（开源 embedding 即可，不需训）| **中期值得**：若产品要支持英文/日文文档，这是基础设施 |

### 每条建议自评（spec §6.6 必填）

每条建议下面 **预期收益（文档名+模式）/ 改造代价 / 回归风险与缓解** 三项已在表内完整覆盖。

---

### 3.5 L2 设计抉择记录（撤回 L2-1）

**抉择**：L2-1「Normalizer 加可选段内切分前置」**永久否决**，不在未来路线上。

**底层原则**：**Parser 是"忠实表达者"，不是"编辑者"**

| 边界 | Parser 该做 | Parser 不该做 |
|---|---|---|
| 段落粒度 | 1 docx paragraph ↔ 1 IR block ↔ 1 ParsedNode | 切分 / 合并段落 |
| 标题判定 | 二元判定：本段是 heading 还是 content（按 styles / 编号 / 启发式）| 推断"前 5 字是标题、后 80 字是内容"|
| 顺序 | 按 docx 原序输出 | 重排、归位 |
| 内容改写 | 0（HTML 透传）| 改文本、补缺、删冗 |

该原则与 spec [`word-parser-solution.md`](word-parser-solution.md) §6 顺序保真不变量一致：

> IR 块流 = 原 docx XML child order 的同构投影。Normalizer 不重排，Structurer 仅在标题位置切分章节，不重排内容块。

**为什么 L2-1 违反此原则**：

- L2-1 把原 docx 1 个段落（如 `3.1质量部是记录的归口管理部门...`）切成 IR 中 2 个块（heading "3.1 质量部" + content "是记录..."）
- 这是 **1:N 解读**，不是 **1:1 投影**
- 切分点判定（"："/"。"/"，" 之后？前 N 字？）是**算法替用户做的编辑决策**，违反"决策权归用户"

**该问题的正确解决路径 — UI 侧（不动 parser）**：

| 问题 | UI 解决方式 | 实现负担 |
|---|---|---|
| 融合式 chapter 标题过长撑爆树 | 树标题字段超 N 字截断 + tooltip 显示全文 | 纯展示，0 数据改动 |
| 用户想把长标题改为内容 | 类型转换按钮：chapter → content（已有"标记模式"基础设施）| UI 增强 |
| 用户想拆"前缀作标题、后缀作内容" | 编辑器内手势：选中分隔符位置后按热键 split | UI 增强 |
| 用户想批量处理同模式的融合式段 | 复用 `detected_patterns` + 模式批量提升 UI | UI 已有，需打磨 |

**决策权归属**是关键区别：UI 切分是**用户主导**，parser 切分是**算法猜**。本原则要前者。

**对未来路线的影响**：

- L2-1 永久否决
- L2-2 ConfidenceScorer / L2-3 ResolverChain 不违反原则，但因无紧迫痛点，暂缓
- 融合式相关 UX 改进转向**前端编辑能力增强**，单独 spec 处理（见 [`docs/superpowers/specs/2026-05-27-frontend-editing-affordances-design.md`](superpowers/specs/2026-05-27-frontend-editing-affordances-design.md)）

---

## 4. 决策建议

**下一步建议做：L1 第 3 条「Trait based 启发式信号注册表」**

**理由**：

1. **价值最高**：本闭环 4 轮改动中 3 轮涉及 score_block 内部权重/逻辑微调；如果再做一轮（如 spec §C.10 残留的 `第X条` 长段问题），重构后会更易迭代——加一个 ChapterPositionSignal 不用动主路径。
2. **风险最低**：纯内部重构，对外 API（chapters[] / confidence_tier）零变化。前端不受影响。
3. **代价可控**：1-2 个工作日，单测保活，可以一次完成。
4. **奠基**：是 L2「ConfidenceScorer 独立阶段」的子集，先把信号层解耦，scorer 拆分自然水到渠成。

**不建议立即做的**（按理由）：

- **L2-1 段内切分**：风险太高（动 IR），且 mainline R=0.86 已达标，融合式整段保留是可接受的产品形态（用户可在 UI 里手动拆，模式批量也能加速）。等业务侧反馈强烈需求再考虑。
- **L3 全部**：当前规则版 P=0.98 / R=0.86 已突破阈值；ML 接管要 2-3 周训练，ROI 不正。除非业务扩到多语种或非 SOP 类文档。

**佐证文档/模式**：
- **L1 拆 SignalCollector 的直接受益**：02记录融合式（`3.1质量部...`）的 r3 三处改动；电厂署名 FP 的 r4 改动；都是 score_block 加几行的事，但因为现在魔术数字散，调一个参数要 trace 多个 if，导致 r3 还出过一个 bug（depth=2 没生效，因为 weak_heading kind 路径短路了）。
- **L1 NumberingProfile 的应用场景**：若将来要支持 IEC 国际标准（"5.1" "5.1.1" 但用 dot 而非空格分隔），或医药 GMP（"a.1" / "(a)1"），无需改 classify_numbering 主体。

---

## 附：交付物清单

| 交付物 | 路径 |
|---|---|
| 设计 spec | `docs/superpowers/specs/2026-05-27-word-parser-polish-design.md` |
| 实施 plan | `docs/superpowers/plans/2026-05-27-word-parser-polish-eval.md` |
| 调参日志 | `docs/parser-tuning-log.md` |
| 综合评估（本文档）| `docs/parser-comprehensive-evaluation.md` |
| Eval harness | `scripts/eval_parser.py` + `scripts/eval/` |
| GT fixtures | `tests/fixtures/eval_gt/manual/*.json` (6 份) + `template_ack/*.json` (3 份) |
| 最终 metrics | `.eval-reports/r4-disable-heuristic-when-styled/` (gitignored) |
| MCP 截图 | `.verify-screenshots/eval-r4-S4-02jilu.png`, `eval-r4-S0-gongsi.png` |
| 单测 | `backend/tests/unit/parser/` 66 个 + `scripts/eval/tests/` 35 个 |

**Git 提交记录（11 commits 在 `feat/word-parser-polish-eval` 分支）**：

```
1e5b456 docs(tuning): 调参回路完整 log
7832a7b tune(parser): styled doc 关闭启发式 [r4]
03c74c8 fix(eval-gt): 补全 CW-WI + 01-公司环境
6d5aed6 tune(parser): depth>=2 编号 unambiguous [r3]
c07b74e tune(parser): LOW + heading 编号才升 [r2]
17f315b chore(eval): 修 GT body_start + 初始化 tuning log
a39bf2d feat(eval): CLI 入口
5c78278 tune(parser): list 标记 hard veto [r1]
... (Task 1-7 commits)
1217c01 docs(plan): 实施计划
6a9fdb7 docs(spec): 设计 spec
```
