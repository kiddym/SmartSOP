# Word 解析器打磨：评测脚手架 + 调参闭环 设计

**日期：** 2026-05-27
**状态：** 待批准
**作者：** 协作设计（cui_yuming + Claude）

## 背景与目标

`backend/app/parser/` 已是经过一轮 grill + 36 份样本验证的三阶段实现（Normalizer → Structurer → Serializer），现行能力（见 `docs/word-parser-solution.md`）：

- **5 份标准 SOP**：styles.xml 反查 5/5 = 100% 命中；
- **5 份无格式 SOP**：v3 自动 P=1.00 / R=0.70，选择性模式批量后接近 F1≈1.0；
- **26 份 QMS 程序（同模板无格式）**：v4 编号字典修复 `N、` 顿号歧义后，body_start 全修正，QMS doc01 GT P=1.00 / R=0.69 / FP=0。

现状两个问题：

1. **指标只散落在多份 `scripts/validate_*.py` 里**，每次跑要手动拼，**没有跨 36 份的统一基线**，每轮调参看不到纵向 diff。
2. **R≈0.70 离严强阈值还差**，关键缺口已定位（"融合式子标题 `N.N、xxx：正文`"等），但缺一个能把"改这里 → 升这里 / 退这里"量化到分的脚手架。

**目标：** 搭一个支撑"测量 + 调参 + 不退化"高频迭代的闭环，在严强阈值下把 36 份样本拉齐，再综合评估解析器现状并提出重构建议。

**严强阈值（达标即闭环结束）：**

- `title_P_micro ≥ 0.98`
- `title_R_micro ≥ 0.85`，且 **不允许任何单份文档 R < 0.6**
- `hierarchy_micro ≥ 0.95`
- `content_cov_micro ≥ 0.98`

## 范围

**做：**

- **新增 `scripts/eval_parser.py`**：36 份 docx → GT 对比 → 三指标（per-doc + micro/macro）→ 报告 + baseline diff。
- **新增 `tests/fixtures/eval_gt/`**：固化 Tier 1 自动 GT + Tier 2 6 份人工 GT + Tier 3 3 份人工 GT。
- **解析器调参迭代**：限定改 `backend/app/parser/heading_detector.py`、`backend/app/parser/structurer.py`、`backend/app/parser/styles.py`、`backend/app/parser/body_start.py`、`config/heading_synonyms.yaml`。
- **MCP 浏览器抽样验收**：固定 6 份关键样本，每轮高风险改动后强制走一遍。
- **新增单测**：把每轮发现的"应识别但漏 / 不该识别但中"的案例固化为单测。
- **综合评估文档**：闭环结束后产出，含重构建议（L0-L3 分级）。

**不做：**

- 解析器三阶段架构、IR 形态、HTML schema 改造（仅微调评分与字典）；
- 前端纠偏 UI（review panel / 模式批量按钮）改动；
- 图片 / 表格的**完整性**比对纳入达标判定（C001/C002 已有，仅作 per_doc 附加信号）；
- `standard` 模式调优（仅作 sanity 一次健康检查）；
- 性能调优（30s 超时 / 上传速度）。

---

## §1 评测 harness 形态

新增 `scripts/eval_parser.py`，**纯新增**，不动现有 `scripts/validate_*.py`（便于回滚 + 保留历史对照）。

### 1.1 CLI 形态

```
uv run python scripts/eval_parser.py
    [--subset all|standard|unstyled|qms]
    [--docs <glob>]
    [--mode standard|smart]            # 默认 smart
    [--baseline <prev_run.json>]       # 出 diff
    [--out .eval-reports/<ts>/]
```

### 1.2 流水线（每份 docx）

```
1. load_gt(docx)   → GT outline + content text  （三种来源，见 §2）
2. parse(docx)     → 直接 import backend 函数，不走 HTTP
3. compare(gt, parsed) → 三指标 + detected_by / warnings 留档
```

**关键决定 — 不走 HTTP**：直接 `from app.parser import parse_docx; result = parse_docx(path, mode='smart')`。理由：一份 docx 评测从 ~2s → ~100ms，避免起后端进程、避免上传 token 折腾，36 份一轮 < 5 秒。HTTP 路径在 §5 MCP 抽样时才会走真实接口。

### 1.3 产出目录

```
.eval-reports/2026-05-27-1240/
  ├── summary.md         # 大表：per-doc + micro/macro 汇总 + 阈值红绿灯
  ├── summary.json       # 机器可读，下一轮 --baseline 用
  ├── diff_vs_baseline.md  # 三指标逐份升降 + 新增/解决的失败
  └── per_doc/<name>.json  # 单份详细：FP/FN 标题清单、层级 mismatch、content gap
```

`.eval-reports/` 加进 `.gitignore`（不入仓）。

### 1.4 baseline diff 必出

每轮新报告强制对上一轮做 diff（哪些文档 R 升了几个点、哪些之前过的现在退化了），不靠肉眼比 markdown。

### 1.5 默认 `smart` 模式

这是产品线上模式；`standard` 仅作严格样式检测的一次性健康检查，**不进迭代**。

### 1.6 per_doc 详细 JSON

列 FP/FN 完整原文 + 上下文，下一轮一眼定位失败模式（融合式子标题 / 页眉表格混入 / 封面误判等）。

---

## §2 Ground truth 分层

三档来源，每档独立函数 `load_gt_<tier>(docx_path) -> GroundTruth`，统一返回结构：

```python
@dataclass
class GtChapter:
    title: str        # normalize 后的标题文本
    level: int        # 1 | 2 | 3
    source_idx: int   # 原 docx 段落顺序索引

@dataclass
class GroundTruth:
    docx_path: Path
    tier: Literal["style", "manual", "template"]
    chapters: list[GtChapter]      # 扁平有序
    body_text: str                 # 拼接正文段落（不含标题、不含页眉）
```

### Tier 1 · style 派生（自动；5 份标准 SOP）

`load_gt_style(docx)`：
- lxml 直接遍历 `document.xml` body 段落；
- 对每个段落，调 `app.parser.styles.classify_with_source`（已实现的 4 级反查，与解析器同一套），命中 1-3 级 → 进 GT；4-6 级压到 3；
- body_text = 所有非标题段落 `<w:t>` 文本拼接，去页眉/页脚 part；
- 若全文 0 命中 → 报错"该文档非 style tier，请用 Tier 2/3"。

> **复用解析器的 styles 模块**但只用它判 heading 名/outlineLvl/based_on——不接入启发式。这保证了 styles 反查的 bug 修复在 GT 和 parser 两端同步生效；但启发式部分是被评测对象，绝不进 GT。

### Tier 2 · manual 复用（6 份；5 份无格式 + QMS `01-公司环境分析控制程序.docx`）

`load_gt_manual(docx)`：从已有 `scripts/validate_unstyled_v3.py` 顶端的 `GROUND_TRUTH = {...}` 字典里提取硬编码 GT，写入 `tests/fixtures/eval_gt/manual/<doc>.json`。

- 一次性迁完，便于版本化；
- **level 字段需补全**（原脚本只标 title 集合，没标 level）：我读 docx 后从编号深度或字号秩推断 level，给你一份 6 份 GT 的 review-list ack 后入库；
- body_text 同 Tier 1 用 lxml 拼。

### Tier 3 · template 归纳（24 份；其余 QMS SOP，不含目录文件）

QMS 共 26 份（25 份 SOP + 1 份 `程序文件目录.docx`，目录非 SOP 单独走 §2 异常处理），同模板高度同构。流程：

1. 把 `01-公司环境分析控制程序.docx` 的 manual GT（Tier 2 已有）当 anchor，提取 L1/L2/L3 编号深度模式（`1.`~`7.` 为 L1；`N.N` 为 L2；`N.N.N` 为 L3）；
2. 对剩 24 份 SOP，用**独立于 parser** 的 `extract_qms_gt(docx)`：纯正则按 `^[1-7]\s*[、.]\s*` / `^[1-7]\.[0-9]+` / `^[1-7]\.[0-9]+\.[0-9]+` 在加粗段里捞，输出候选 outline；
3. **抽样 3 份人工 ack**：我选 `05-基础设施控制程序.docx`、`15-标识和可追溯性控制程序.docx`、`25-各级人员质量职责和权限规定.docx`（首/中/尾三档跨度），给你 review-list ack；
4. 其余 21 份记 `tier="template", reviewed=false`，summary.md 用 ⚠️ 标识。

**对冲循环验证嫌疑**：
- Tier 3 抽取器**先于 parser 改动写完并冻结**，且独立用 anchor doc 归纳，不复用 parser 的 `classify_numbering`；
- summary.md 把 Tier 1/2/3 三档分开报，aggregate 也按档分别给一份；
- **严强阈值判定按 Tier 1+2 为主线**，Tier 3 作"不退化"约束。

### 异常文档

- `extra doc/程序文件目录.docx`（程序清单/目录，非 SOP）：标记 `expected_empty=true`，eval 单独处理（不计 P/R 分子分母；parser 给 ≥1 章节则在 per_doc 标 `unexpected_chapters_n`，不阻塞达标）。

---

## §3 三指标算法

三指标都按 per-doc 算 → 两种汇总：**micro**（按总标题数加权）和 **macro**（按文档数平均）。`summary.md` 同时报两套，严强阈值以 micro 为准。

### 3.1 Title P / R / F1

**对齐方式**：标题文本 normalize 后**有序 LCS 对齐**，不做集合对齐。

- normalize：`re.sub(r"\s+", "", title).strip().lower()`（去全/半空白 + 全/半角统一 + 大小写）；
- 解析器 `chapters[]` 扁平化为 `[normalized_title]` 序列；GT 同样；
- LCS 找对齐对；
- TP = 对齐成功；FN = GT 有但未对齐；FP = parsed 有但未对齐；
- P = TP / (TP+FP)，R = TP / (TP+FN)，F1 = 2PR/(P+R)。

**为什么不用集合**：QMS 模板里 `定义` 这种短标题在多份重复，子标题 `N.N、xxx` 在不同章节下可能重名。集合对齐会忽略顺序错位；LCS 兼顾顺序敏感 + 容忍单点漂移。

### 3.2 hierarchy_accuracy

仅在 LCS 对齐成功的 TP 上算（FP/FN 不参与）：

- 每对 `(gt_i, parsed_j)`：`hit = (gt_i.level == parsed_j.level)`；
- per-doc accuracy = hits / |TP|；
- micro = Σ hits / Σ |TP|，macro = mean(per-doc)。

不评测 FP 的层级（已是错的）；不评测 FN 的层级（无 level 可比）。

### 3.3 content_coverage

衡量"原文正文文本在解析结果里有多少能找回"，目标 0.98。

- **gt_body_text** = GT `body_text`（非标题正文段落 + 表格 cell 文本；不含页眉页脚、不含标题文本）；
- **parsed_body_text** = 解析器 `chapters[]` 递归收集所有 `content_type == 'content'` 节点的 `rich_content` 后 `BeautifulSoup(...).get_text()`，再 normalize；
- **3-gram 字符集合 IoU**：
  - `gt_grams = set(zip(gt_text, gt_text[1:], gt_text[2:]))`
  - `parsed_grams = ...`
  - coverage = `|gt_grams ∩ parsed_grams| / |gt_grams|`
- normalize：去空白、CJK 全角 → 半角；**不去标点**（标点是"是否提到表格 cell 边界"的弱信号）。

**为什么 3-gram**：字符集合在中文上太宽松；LCS 在 30k 字符正文上 O(N²) 爆掉；3-gram 在 30k 字上 ≈ 几万到十几万元素，set 运算 < 100ms，且能抓住短句缺失。

### 3.4 阈值红绿灯（写进 summary.md 顶部）

```
=== 严强阈值（必须全 ✅ 才算闭环结束）===
[✅/❌] title_P_micro ≥ 0.98     当前: 0.xxxx
[✅/❌] title_R_micro ≥ 0.85     当前: 0.xxxx
[✅/❌] no_doc_with_R < 0.6      最低分文档: xxx (R=0.xx)
[✅/❌] hierarchy_micro ≥ 0.95   当前: 0.xxxx
[✅/❌] content_cov_micro ≥ 0.98 当前: 0.xxxx
```

### 3.5 特殊处理

- `expected_empty=true`：不计 P/R 分子分母，独立 warning；
- Tier 3 未抽样部分：单独报，不进达标判定；
- C001/C002（图片/表格完整性）：per_doc 附加信号，不进达标。

---

## §4 调参回路

每轮固定 6 步：

```
[1] uv run python scripts/eval_parser.py --baseline <last_run.json>
     ↓ < 5s 出报告
[2] 看 summary.md 红绿灯 + diff_vs_baseline.md
     - 指标退化 → 立刻 git stash + 找罪魁，不允许带退化继续
     - 不升不退 → 看 per_doc 失败明细
[3] 选 1-2 个失败模式定向改（一轮不打两枪以上，便于 attribution）
[4] 跑 backend/tests/unit/parser/ pytest
     - 任何单测红 → 回 [3]
[5] 再跑 eval_parser，对照 diff:
     - 改动文档的指标必须升
     - 其它文档任一指标不允许退（micro/macro/per-doc 全部）
     - 退化 → revert，回 [3]
[6] 收尾：
     - commit message: "tune(parser): <模式名> → +R Δ0.xx / +F1 Δ0.xx"
     - 在 docs/parser-tuning-log.md 追加一行（见 §4.3）
```

### 4.1 失败模式分类

| 类 | 改动位点 |
|---|---|
| a. 编号字典 miss / 误判 | `heading_detector._RE_*` + `classify_numbering` |
| b. 启发式分数偏差 | `score_block` 权重 |
| c. body_start 跑偏 | `body_start.py` 决策树 |
| d. 样式反查链 miss | `styles.classify_with_source` |
| e. 同义词词典缺项 | `config/heading_synonyms.yaml` |
| f. structurer 边界 / level cap | `structurer._classify_heading` / `_MAX_CHAPTER_LEVEL` |

### 4.2 优先级（按预期 ROI 排，避免长尾耗时）

| 优先级 | 触发条件 | 典型例子 |
|---|---|---|
| P0 | 任一指标退化 | 任何 |
| P1 | 单一改动可同时升 ≥3 份文档 R | 编号字典补一条、同义词补一条 |
| P2 | 仅升 1 份文档 R 但缺口 > 0.2 | 某份独有的模式 |
| P3 | 涉及"融合式子标题"等需要切块的改动 | structurer 内做段内切分 |
| P4 | 个位数字符的 content_coverage 缺口 | 软连字符、零宽空格 |

**P3 改动后强制走一次 §5 MCP 抽样验收**（动 structurer 段切分形态，前端章节树可能炸），不通过则 revert。

### 4.3 调参日志 `docs/parser-tuning-log.md`

每轮一行，强制写 trade-off 理由：

```
| 轮 | 时间 | 改动 | 改的文件 | micro P/R/F1 | hierarchy | content_cov | 备注/trade-off |
| 0  | base | -    | -        | 1.00/0.74/.85| 0.93      | 0.96         | 起点 |
| 1  | …    | 补编号字典 "N+空格 weak→heading"（限粗体+短段）| heading_detector.py | 1.00/0.79/.88 | 0.94 | 0.97 | doc02/05/15 R+0.12，无回退 |
```

### 4.4 Trade-off 自决权

用户授权我自决：某份 doc 升 0.3 / 另一份退 0.05 这类 trade-off 我直接判，**tuning log 每行强制写 trade-off 理由**（事后可审）。

### 4.5 退出条件

1. **达标退出**：§3.4 红绿灯全 ✅，且 §5 MCP 抽样过 → 进 §6 收尾；
2. **停滞退出**：连续 3 轮 micro 指标 Δ < 0.005 → 我主动写一份"剩余失败模式 + 各自预期收益和风险"，转去问用户是否继续、降阈值、还是改方案。

---

## §5 MCP 浏览器抽样验收

**触发**：每一轮 eval 通过 + 失败模式属 P3 时**强制**；其它轮按需（用户已授权"觉得有必要就开浏览器"）。

### 5.1 抽样集（固定 6 份）

| 编号 | 文件 | 代表性 |
|---|---|---|
| S1 | `typical word doc/1_程序模板.docx` | 标准 heading 1-5（baseline 哨兵）|
| S2 | `typical word doc/TP试验程序.docx` | 中文同义词"章节标题"（同义词词典保活）|
| S3 | `typical word doc/电厂管理巡视规定.docx` | 标准 heading 1-2 + 较深表格嵌套 |
| S4 | `typical word doc/无格式标题word/02记录控制程序.docx` | 无格式 + `N+空格` 模式 |
| S5 | `typical word doc/无格式标题word/CW-WI-7.4-01外发作业指导书及质量控制程序.docx` | 无格式 + 封面/签名块易误判 |
| S6 | `typical word doc/extra doc/05-基础设施控制程序.docx` | QMS 模板 + `N、x` weak heading |

### 5.2 每份的验收脚本

```
[1] mcp__chrome-devtools__navigate_page → http://localhost:5173/procedures/new-from-word
[2] mcp__chrome-devtools__upload_file   → 该 docx
[3] mcp__chrome-devtools__wait_for      → 跳到编辑器（章节树渲染）
[4] mcp__chrome-devtools__take_screenshot → .verify-screenshots/eval-r<轮号>-S<编号>.png
[5] mcp__chrome-devtools__evaluate_script:
    - 读 Pinia store（chapters 树），dump 成 JSON
    - 与本轮 eval_parser.py 输出的 same-doc per_doc/<name>.json 对比 → 必须 byte-equal
[6] mcp__chrome-devtools__list_console_messages → 抓异常
[7] 异常或 chapters 不一致 → revert 本轮 commit
```

**第 [5] 步关键**：parsed tree 是否能正确灌到前端、前端是否能不报错地渲染。脚本评测抓不到这种退化。

### 5.3 失败处理

- 截图差异（章节缩进/标记变了）→ 走 visual review，靠 chapters JSON 对比兜底；
- console 有 error → 必 revert，记录到 tuning log 备注列；
- 上传 30s 超时 → 单独建 issue 卡片，不阻断本轮。

---

## §6 收尾与风险

### 6.1 闭环结束时的交付物

1. **`.eval-reports/final/summary.md`**：36 份 per-doc 三指标 + micro/macro 汇总；
2. **`docs/parser-tuning-log.md`**：每轮一行的完整调参日志（含 trade-off 备注）；
3. **`tests/fixtures/eval_gt/`**：Tier 1 自动生成（脚本可回放）+ Tier 2 (6 份你 ack) + Tier 3 (3 份你 ack)，固化进 git；
4. **解析器代码改动**：集中在 `backend/app/parser/` 与 `config/heading_synonyms.yaml`，每个 commit message 形如 `tune(parser): <模式名> → +R Δ0.xx / no regression`；
5. **`docs/parser-comprehensive-evaluation.md`**：综合评估 + 重构建议（见 §6.6）。

### 6.2 单测保活

`backend/tests/unit/parser/` 现有单测必须全程绿（§4 第 [4] 步已写入）。新发现的"应识别但漏"或"被误识别"案例**直接加为新单测**，eval harness 只算指标，单测才能在未来回归时第一时间报警。

### 6.3 已识别风险与缓解

| # | 风险 | 缓解 |
|---|---|---|
| R1 | Tier 3 GT 抽取器和 parser 都依赖编号正则 → 循环验证 | (a) Tier 3 抽取器**先于** parser 改动写完并冻结，独立用 anchor doc 归纳；(b) summary.md 三档分报；(c) 严强阈值按 Tier 1+2 为主线，Tier 3 作"不退化"约束 |
| R2 | 融合式 `N.N、xxx：正文` 子标题要切块才能升 R → 改动到 structurer 段切分形态 | 列为 P3，每次改动**强制** §5 MCP 抽样；切块改动单独 commit |
| R3 | content_coverage 在含表格图片的 docx 上可能拿不到 0.98（HTML 序列化引入额外 grams） | 先跑一轮基线测真实差距；若结构性缺口，调整 normalize（剔除 HTML tag 后比对 + 容忍单字符跳变），不调阈值 |
| R5 | trade-off 自决误判 | tuning log 每行强制写 trade-off 理由；§5 截图保留每轮一套 |
| R6 | `extra doc/程序文件目录.docx` 这类非 SOP 文档误进 eval | `expected_empty=true` 标记；新增此类需手动加 flag |

### 6.4 不在本闭环范围

避免范围蔓延，下列明确**不动**：

- 解析器架构（3 阶段、IR 形态、HTML schema）—— 仅微调评分与字典；
- 前端纠偏 UI；
- 图片 / 表格的完整性比对纳入达标判定；
- `standard` 模式调优；
- 性能。

### 6.5 总时长预期

- 搭脚手架 + GT 抽取：1 个工作 session；
- 调参迭代：基线 R≈0.74 → 目标 ≥0.85，预计 5-10 轮，每轮 5-15 分钟思考 + < 5 秒跑测；
- 难关：融合式子标题（R 缺口主因，P3），预计 1-2 轮专门攻关 + MCP 验收。

### 6.6 综合评估与重构建议（交付物 #5）

闭环结束后产出 **`docs/parser-comprehensive-evaluation.md`**，含：

1. **解析器现状画像**
   - 三阶段各自的真实承担与盲区，按"代码行数 vs 价值贡献"打分；
   - 36 份样本上能/不能识别的具体模式清单，与 `word-parser-solution.md` 原设计偏差对账；
   - 每个文件的圈复杂度 + 单测覆盖率 + 改动频次三联指标。

2. **质量画像**
   - 三指标的天花板归因：当前剩多少缺口分别归因到"算法本身"vs"数据 GT 噪音"vs"业务定义模糊"；
   - HIGH/MEDIUM/LOW 三档的实际分布与置信度自洽性（HIGH 是不是真的零误报、LOW 是不是接近随机）。

3. **重构建议（分级）**
   - **L0 微调**（已在闭环里做掉）：编号字典、评分权重、同义词词典；
   - **L1 局部重构**：本闭环里被 hack 但应有更干净抽象的地方（例：评分项现散在 `score_block` 一个函数里，是否拆"信号收集器 + 权重组合器"；编号字典是否抽成可配置的 `NumberingProfile`）；
   - **L2 架构重构**：碰到但没敢动的（例：融合式子标题在 Structurer 阶段切块——是否要在 Normalizer 加可选的"段内切分"前置；置信度计算是否应迁出 Structurer 单独成 `ConfidenceScorer` 阶段）；
   - **L3 数据驱动改造**：闭环里发现"规则越加越乱"的部分，是否应改成小模型/向量召回（不下结论，列 ROI 评估）。

4. **每条建议附 3 项必填**：预期收益（用本闭环里某份失败案例佐证）、改造代价估算、回归风险与缓解。

5. **决策建议**：在 L0/L1/L2/L3 里给一条"下一步建议做哪个"，理由具体到几份文档名 + 几个失败模式。

---

## 实施顺序

1. **`.gitignore` 加 `.eval-reports/`**（避免污染 git）；
2. **写 `scripts/eval_parser.py` 骨架**：CLI + 流水线 + summary.md 输出（先不接 GT 函数，跑通框架）；
3. **写 `load_gt_style` (Tier 1)**：拿标准 5 份跑通端到端基线；
4. **迁 Tier 2 manual GT 到 fixtures**：补 level + 给用户 ack list；
5. **写 `extract_qms_gt` (Tier 3)**：3 份抽样给用户 ack；
6. **跑首轮基线**（`.eval-reports/baseline/`），写入 `parser-tuning-log.md` 第 0 行；
7. **进入调参回路**（§4 六步循环）；
8. **每轮按需启用 §5 MCP 验收**；
9. **达标后写 `parser-comprehensive-evaluation.md`**（交付物 #5）。

---

## 决策记录

| # | 决策 | 选项 | 选择 | 理由 |
|---|---|---|---|---|
| Q1 | 工作目标 | 测量+调参 / 仅端到端实测 / 仅脚本调参 | 测量+调参闭环 | 严强阈值 + 36 份样本需要纵向 diff |
| Q2 | 成功率口径 | 三维度分开 / F1 为主 / 人机协同口径 | 三维度分开 | 章节、多级、内容各自归因，避免单指标遮蔽 |
| Q3 | GT 建法 | 分层提取 / 仅现有 GT / 全手工 | 分层提取 | 平衡自动化与人工抽样成本 |
| Q4 | MCP 角色 | 每轮抽样 / 全 36 走浏览器 / 仅终了验收 | 每轮抽样验收 | UI 退化兜底 + token 经济 |
| Q5 | 阈值 | 严强 / 温和 / 不退化 | 严强 | 用户明示 |
| Q6 | 评测脚本是否走 HTTP | 走 / 直 import | 直 import | 36 份 < 5s vs 起后端调度 |
| Q7 | reports 目录 | `reports/` / `.eval-reports/` / `docs/` | `.eval-reports/` gitignore | 大量临时产物，不入仓 |
| Q8 | Tier 2 level 补全 | 我先抽 ack / 用户先指定 | 我抽 ack | 用户授权 |
| Q9 | Tier 3 抽样选哪 3 份 | 我选 / 用户选 | 我选（doc05/15/25 跨度）| 用户授权 |
| Q10 | 标题对齐 | LCS 顺序 / 集合 / 嵌入相似 | LCS 严格 normalize | QMS 短标题重名需顺序敏感 |
| Q11 | content_cov 分母 | GT grams / 并集 | GT grams | "GT 里有多少被覆盖" |
| Q12 | trade-off 自决权 | 默认 revert / 自决 + 记日志 | 自决 + tuning log 强制写理由 | 用户授权 |
