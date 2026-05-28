# 统一节点模型(ProcedureNode)— 用 heading_level 取代 chapter/content 三分制与层级标定模式

**日期:** 2026-05-28
**状态:** 已确认(brainstorm 完成 / 待 writing-plans)
**作者:** 协作设计(cui_yuming + Claude)
**激进度:** 架构级(用户明确授权可质疑 parser→DB 三分模型本身)

## 一句话

把 `ProcedureChapter` 表与 `ProcedureStep.kind∈{content,step}` 的分裂合并成**单一 `ProcedureNode`**:每个节点带一个 `heading_level: int|null`(null=正文、1..N=章节层级)和 `kind: 'node'|'step'`(step 正交)。树形态由 `sort_order + heading_level` **派生**(outliner 语义),不再存 `parent_id`。"章节↔内容转换"退化为**改一个字段**,从根上删除"层级标定模式"整条链路与今天刚定的 auto-extract/flatten 设计。

---

## 背景:三条架构级质疑

本设计源于对现有 Word 解析 + 手动调节链路的架构质疑。三条:

### 🔴 #1 — `kind` 三分制是被 parser 强行硬决断的,但 parser 只能区分一个 boolean

- Parser(`backend/app/parser/result.py:21`)输出只有 `content_type: "chapter" | "content"`,本质就是"这段是不是 heading"的 boolean;`kind="step"` 根本不是 parser 产物,而是人后期把 content 升级(加 `input_schema`)。
- 但落库时模型搞了三分:`ProcedureChapter` 独立表 + `ProcedureStep.kind∈{content,step}`。
- 为维护三分制,写了 ~1500 行 parser(`heading_detector.py` 281 + `normalizer.py` 506 + `structurer.py` 265 + 周边)去"决断"每段是什么;又写了 305 行 `layer_apply_service.py` + `LayerApplyResult/extracted_titles/collapsed_chapters/chapter_map` 去"反悔"决断。
- **根因**:把"是不是标题"和"是不是表单 step"塞进同一枚举,parser 必须二选一(必然错),修错只能走有损"转换"。

### 🔴 #2 — "层级标定模式"是 #1 的派生组织成本

- `layerMark.ts` + `LayerRow` + `effectiveRole` + `computeLayerUpdates` + `computeLayerIndents` + `validateLayerQ25` + `applyLayerRoles` RPC + 后端三相事务(Phase A/B/C) + 5 份 spec。
- 模式存在的唯一理由:promote/demote 是"魔法操作",不能让用户在普通树里随便点。
- 反问:若模型不区分 chapter/content/step,层级调整只是改 `heading_level` 字段——没有任何理由要独立模式。同级互斥(Q25)也消失,因为"同级"是 `heading_level` 算出来的,物理上构造不出违反状态。

### 🟡 #3 — auto-extract 50 码点阈值 + round-trip 非对称是 #1 的下游症状

- `2026-05-28-content-chapter-roundtrip-design.md` 显式承认 round-trip 2 不严格(加 `test_roundtrip_2_explicitly_breaks` 防误改回),50 码点是经验值。
- 根因在 `title`(plain text)与 `body`(HTML)的**类型分裂**:promote 要 HTML→text 抽取(有损),demote 要 text→HTML 包 `<p>` flatten(mutate)。
- 若模型只有一个 `body: rich` + 一个 `heading_level`,根本没有"抽取/flatten"两个动作,promote/demote 就是一次字段写,严格 round-trip 天然成立。

**结论**:#2、#3 都是 #1 的下游。本设计动 #1。

---

## 目标

1. **删除三分制的物理根源**:chapter/content 合并为一种节点 + `heading_level` 字段。
2. **"转换"退化为一次 PATCH**:无事务状态机、无 mirror-shape、无 Q25、无 auto-extract/flatten;严格 round-trip 天然成立。
3. **删除"层级标定模式"**:层级调整回归普通行内编辑,4 条输入路径并行(见 §6)。
4. **大幅瘦身**:parser 从建树降级为产扁平 list;`layer_apply_service` 几乎全删。
5. **保留 step 的业务独立性**:`kind='step'` 正交于 `heading_level`,执行/sign-off 不受影响。

## 非目标

- ❌ **不做数据迁移脚本**:无生产数据(用户确认),一次性重建表 + 重 seed(见 §8)。
- ❌ **不改 step 的执行/sign-off 语义**:本期只改结构存储,`input_schema`/表单字段/签核流程读取口径适配,语义不动。
- ❌ **不重做 PDF 视觉**:沿用 `pdf-content-no-title` 的决策(content 无编号无标题内联),仅适配数据来源从两表变一表。
- ❌ **不做 overlay 范式**(方案 C):本期是 B,不推翻结构化解析。
- ❌ **不动 `mark_service.py`(通用标记/级联选择)**:它服务附件批量等场景,与层级标定不是一回事,本期不删,仅评估其对 chapter/content 的引用是否需改读取口径。

---

## §1 数据模型

### 1.1 新表 `ProcedureNode`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str(主键) | 稳定 id,附件/sign-off 引用它 |
| `procedure_id` | FK | 所属 procedure |
| `sort_order` | int | **全局有序**(per procedure 的扁平位置),不再 per-chapter。用 `sequence_generator` gap 序(1000,2000,…) |
| `heading_level` | int \| null | null=正文;1/2/3/4…=章节层级 |
| `kind` | str | `'node'` \| `'step'` |
| `body` | text(HTML) | rich。heading 的"标题"= body 第一个块级元素的文本(派生,见 §2.3) |
| `input_schema` | JSON | 仅 `kind='step'` 非空(沿用 `_invariants.py` 现有 invariant) |
| `attachment_marks` | JSON | 沿用现状 |
| `revision` | int | 乐观锁(沿用 `optimistic_lock.py` 模式) |
| `is_active` / `deleted_at` | bool / ts | 软删 |

### 1.2 删除

- `ProcedureChapter` 表(整张)。
- `ProcedureStep.title` 字段(标题改由 body 第一段派生)。
- **`parent_id` 不存**(见 §2)。

### 1.3 不变量(`_invariants.py` 升级)

1. `kind='node'` → `input_schema == {}`(沿用现有 content invariant)。
2. `kind='step'` → `heading_level IS NULL`(step 是叶子表单,不能是标题)。
3. `heading_level` 若非 null,必须 ≥1 的整数(无上界,跳级允许,见 §3.2)。
4. `body` 可为空(空 heading = 占位章节,渲染时标题显示"未命名");可 rich/多段(Q1 决策)。

---

## §2 树派生(不存 parent_id)

### 2.1 决策:派生而非存储

父子关系由 `sort_order + heading_level` 用一次栈扫**算出**,DB 不存 `parent_id`。理由:从根上消灭"parent_id 与 heading_level 不同步"这一整类 bug。API 读取时附带派生的 `parent_id`/`depth` 供前端渲染,但它们不是持久字段。

### 2.2 派生算法(O(n) 栈扫)

```python
def build_tree(nodes: list[Node]) -> list[TreeNode]:
    """nodes 已按 sort_order 升序。返回带 parent_id/children 的派生树。"""
    stack: list[Node] = []  # 当前祖先链(全是 heading)
    roots: list[Node] = []
    for n in nodes:
        if n.heading_level is None:
            # 正文 / step:挂到栈顶 heading,否则挂根
            parent = stack[-1] if stack else None
        else:
            # heading:弹栈直到栈顶 level < 本节点 level
            while stack and stack[-1].heading_level >= n.heading_level:
                stack.pop()
            parent = stack[-1] if stack else None
            stack.append(n)
        attach(n, parent)  # parent is None → roots.append(n)
    return roots
```

复用现有 `layer_walk.py` 思路(它本就是"层级标定 walk")改写为本算法,或新建 `node_tree.py`,删 `layer_walk.py`。

### 2.3 标题派生与渲染

- **树行标签** = `body` 第一个块级元素的纯文本,截断到 80 码点仅供显示(全文仍在 body)。空 body → 显示"未命名章节"。
- **编号**(`numbering_service`)从派生树算:仅 heading 节点参与 "3.1.2" 计数;正文/step 不编号(沿用现状)。
- heading 的 body 若多段:第一段是标题,其余段是该章节的"引言正文",渲染在标题之下、子节点之上。数据层不约束 heading body 形态(保证 §4 严格 round-trip);编辑器**可**后续加"heading 内回车拆出新正文行"的 nicety,本期不做。

### 2.4 跳级处理

算法 2.2 天然吸收跳级:L1 后直接 L3,L3 弹栈找到 L1 作 parent。渲染按 `heading_level` 数字缩进。跳级不阻拦,仅在发布检查/校验出**软警告**(§3.2)。

---

## §3 转换语义

### 3.1 转换 = 一次字段写

```
PATCH /nodes/{id}  { heading_level: 2 }        # 正文 → L2 章节
PATCH /nodes/{id}  { heading_level: null }     # 章节 → 正文
PATCH /nodes/{id}  { kind: 'step', input_schema: {...} }   # 升级表单步骤
PATCH /nodes/{id}  { kind: 'node', input_schema: {} }      # step 退回普通节点
```

无 promote/demote 事务、无 mirror-shape、无 Q25、无 auto-extract/flatten、无 `extracted_titles`/`collapsed_chapters` map。

### 3.2 降级:子节点自动上提(Q2 决策)

降级一个 heading(`heading_level: 2 → null`)**不移动任何子节点数据**——子节点的"父"是派生的,降级后它们自动归到上一个 heading 名下。示例:

```
[行0] L1: A
[行1] L2: B   ← 降为正文
[行2] null: x
[行3] null: y
[行4] L2: C
```

行 1 `heading_level: 2→null` 后,派生树:B、x、y 都成 A 的子(B 不再是 heading,x/y 找到的最近 heading 变成 A);C 仍是 A 的子。**零数据搬移**。

### 3.3 严格 round-trip(Q1 决策的回报)

```
content(body="<p>3.1 质量部</p>")
  ── 设 heading_level=2 ──→  L2 heading(body="<p>3.1 质量部</p>")
  ── 设 heading_level=null ─→  content(body="<p>3.1 质量部</p>")   ✓ 完全回到起点
```

`body` 全程不变,只动 `heading_level`。多段 rich body 同样严格 round-trip。**这是相对 `2026-05-28-content-chapter-roundtrip` 的根本改进:它的 round-trip 2 显式不严格,本设计两条路径都严格。**

### 3.4 跳级软警告

设级时不阻拦跳级;发布检查清单(`PublishChecklistDialog`)/校验里列一条软警告"第 N 节从 L1 直接跳到 L3"。用户可忽略发布。

### 3.5 升级:节点原地变身 + 接管后续正文(§3.2 降级的镜像)

升级**不新建任何节点**,也不"把内容搬进新章节"。被升级的节点自己把 `heading_level` 从 `null` 改成数字——**同一个 id、同一份 `body`,body 原地不动**。它升级后渲染为 heading,树里的标题取 body 第一段(§2.3),右侧详情仍展示同一份 body(详见 §6.2 NodeDetailPanel)。

唯一的结构副作用是降级"子上提"的镜像:节点成为 heading 后,**紧跟其后、尚无更高/同级 heading 拦截的正文/step 自动成为它的子**(派生树重新计算,零数据搬移)。

```
升级前(x 是正文,与 y/z 平级,都是 A 的子):
[行0] L2  A
[行1] •   x   ← 升 L3
[行2] •   y
[行3] •   z
[行4] L2  B

升级后(x 成 L3,y/z 的"最近上方 heading"变成 x,自动归到 x 名下):
[行0] L2  A
[行1]   L3  x      ← x.body/id/sort_order 全没动,只是 heading_level: null→3
[行2]     • y      ← y/z 数据没动,派生树里 parent 从 A 变成 x
[行3]     • z
[行4] L2  B
```

边界:y/z 被接管,是因为它们紧跟 x 且后面没有更高/同级 heading 挡开。若 x 后面紧接 `L2 B`,则 x 升 L3 后**无子**(B 是同级 heading,不归 x 管)。

round-trip:把 x 降回 `null`,y/z 自动归还给 A,body 字节级不变(与 §3.3 一致)。

```
点击 x —— 升级前后右侧详情几乎一致(同一富文本框、同一份 body):
  升级前:层级 [正文 ▼]  正文: ┌ 3.1 质量部是记录的归口管理部门 ┐
  升级后:层级 [L3   ▼]  正文: └ 3.1 质量部是记录的归口管理部门 ┘
无独立"标题输入框";标题 = body 第一段(即树里那行标签)。
```

---

## §4 API 设计

| 端点 | 用途 |
|---|---|
| `GET /procedures/{id}/nodes` | 返回扁平 list(按 sort_order) + 派生 `parent_id`/`depth`/编号,供前端渲染 |
| `PATCH /nodes/{id}` | 单字段更新:`heading_level?` / `body?` / `kind?` / `input_schema?` / `attachment_marks?`。带 `revision` 乐观锁。**这是"转换"的唯一入口** |
| `POST /procedures/{id}/nodes` | 在指定位置插入新节点(给定前驱/后继 id 或目标 sort_order) |
| `DELETE /nodes/{id}` | 软删 |
| `POST /procedures/{id}/nodes/reorder` | 批量写 sort_order(拖拽/移动子树:前端算出受影响行的新 sort_order,后端只落库) |
| `PATCH /procedures/{id}/nodes:batch` | 批量改 `heading_level`(多选浮动条,见 §6 路径 γ) |

**删除**:`applyLayerRoles` / `apply-layer-roles` 端点及 `LayerApplyResult` schema。
**保留待评估**:`convert_to_chapter` / `convert_to_content` 单行端点(无 UI 调用方)直接删,被 `PATCH heading_level` 取代。

### 4.1 移动子树语义

拖拽一个 heading 行 = 移动它的整棵子树(扁平 list 里从该 heading 到"下一个同级或更高级 heading 之前"的连续区间)。前端按派生树算出区间 + 目标插入点,生成新 sort_order 序列,调 `reorder`。后端保持 dumb(只写 sort_order),不重算 heading_level。

---

## §5 Parser 改动

### 5.1 输出降级为扁平 list

- `ParsedNode.content_type: "chapter"|"content"` → `heading_level: int|null`(heading 检测结果直接产出 level 数字,正文产 null)。
- `structurer.py`(265 行,建章节树)→ 删除建树逻辑,改产**扁平有序 list**;树由后端 §2.2 派生。`heading_detector.py` 保留(仍检测 heading + level),但不再决定树形态。
- `normalizer.py`(506 行)凡是为建树服务的段落归并逻辑评估删减;`parser-no-mutation-principle`(段落 1:1、不切不融)继续遵守。

### 5.2 导入落库

`import_service` / `parse_service` 把扁平 list 直接写成 `ProcedureNode` 行(heading→`heading_level=N`,正文→null,全部 `kind='node'`),`sort_order` 按 list 顺序 gap 序赋值。不再建 `ProcedureChapter` 行。

---

## §6 前端改动

### 6.1 4 条输入路径并行(无"模式")

| 路径 | 形态 | 适用 |
|---|---|---|
| α inline chip | 每行行首一个层级 chip,点开下拉「正文/L1/L2/L3/L4/step」,点选即生效 | 新手、单行 |
| β 键盘 | `Cmd+1..4` 设级、`Cmd+0` 设正文、`Tab`/`Shift+Tab` 增减缩进;多选 + 按键批量 | 高频用户 |
| γ 多选浮动条 | 框选/勾选多行 → 浮出工具栏「设为 正文/L1/L2/L3/L4」→ `:batch` | 批量 |
| δ markdown | 行内编辑时行首打 `## ` 升级、heading 行首 `Backspace` 降级 | markdown 习惯者 |

单行操作 ≤1 次点击(或 0 点击键盘);撤销走普通 `Cmd+Z`(行级编辑历史);反馈即时(前端 optimistic + 后端 ack)。

### 6.2 组件合并

- `ChapterTreePanel` + 渲染逻辑 → `NodeTreePanel`(渲染派生树,行带 level chip)。
- `ChapterDetailPanel` + `ContentDetailPanel` → `NodeDetailPanel`(展示 body + heading_level + 若 step 展示 input_schema)。`StepDetailPanel` 的表单字段编辑并入或保留为 NodeDetailPanel 的 step 子区。
- `TreeRow.vue` 加 level chip + 多选 checkbox。

### 6.3 删除

- `layerMark.ts` / `validateLayerQ25` / `computeLayerUpdates` / `computeLayerIndents` / `effectiveRole` / `LayerRow` 类型。
- store `applyLayerRoles` action 及其 spec。
- 层级标定模式的进入/退出 UI、`extracted_titles`/`collapsed_chapters` toast 逻辑。
- `ContentDetailPanel` 的 title placeholder(连同 title 字段)。

### 6.4 评估(可能保留)

- `batchMark.ts` / `mark_service` 对应的通用级联选择:服务附件批量等,**不随层级模式删**;仅检查其对 chapter/content 字段的引用改成 node 读取口径。

---

## §7 下游适配

| 模块 | 适配 |
|---|---|
| PDF(`services/pdf/`) | 从派生树取数据:heading→编号+标题块+引言 body+子;正文/step→body 内联(沿用 `pdf-content-no-title`) |
| `numbering_service` | 从派生树算编号(仅 heading 参与计数) |
| sign-off / `version_flow_service` / `version_service` | 凡引用 `ProcedureChapter`/`ProcedureStep` 的查询改 `ProcedureNode`;node id 稳定,签核记录不丢 |
| `optimistic_lock` | node 级 `revision` 沿用现有 Protocol;结构变更(reorder/level)同样 bump |
| `sequence_generator` | 全局 per-procedure gap 序赋 `sort_order` |
| `attachment_service` | 引用 node id,语义不变;检查 chapter/step 二分引用 |
| `editor_service` / `step_service` / `field_service` | 改读 node;step 字段编辑路径保留 |

---

## §8 迁移策略(无数据,一次性重建)

用户确认无生产数据。**不写 chapter→node 数据迁移脚本。**

1. 新建一个 Alembic revision:`drop_table procedure_chapter`,把 `procedure_step` 重建/改造为 `procedure_node`(加 `heading_level`,删 `title`,`kind` 取值改 `node|step`,`sort_order` 改全局语义),或直接 drop+create `procedure_node` 并废弃旧 step 表。
2. 重写 `seed.py` 产出 `ProcedureNode` 行。
3. 删 `backend/dev.db` 重新建库 + seed(memory `qa-fullsweep-2026-05-25` 的 dev.db 未迁移坑此处一并清掉)。

---

## §9 删除 / 简化清单(回报实体)

**删:**
- `layer_apply_service.py`(305 行)+ `test_layer_apply_service.py`
- `layer_walk.py`(改写为 `node_tree.py` 或并入)
- `chapter_service.py`(并入 node service)
- `ProcedureChapter` model/表;`ProcedureStep.title`
- 前端 `layerMark.ts` / `validateLayerQ25` / `computeLayerUpdates` / `computeLayerIndents` / `LayerRow` / `effectiveRole` / `applyLayerRoles`
- `convert_to_chapter` / `convert_to_content` 端点

**作废 spec(本设计取代):**
- `2026-05-28-content-chapter-roundtrip-design.md`(整份)
- `2026-05-27-layer-overlay-auto-nest-design.md`(层级模式部分)
- `2026-05-24-flat-layer-marking-design.md`
- `2026-05-25-p2c-layer-marking-design.md`
- `2026-05-26-mark-mode-cascade-selection-design.md`(若 mark mode 仅服务层级;若也服务附件则部分保留——实施时确认)

**简化:**
- parser `structurer.py`(265 行,建树→产扁平 list)、`normalizer.py`(506 行,删建树相关归并)
- 编辑器面板 4 个 → 2 个(NodeTree + NodeDetail)

---

## §10 测试策略

### 10.1 后端

- **树派生**(`build_tree`):正常嵌套、跳级(L1→L3)、空 body heading、连续正文、栈弹空(L2 无 L1 前驱时挂根)、step 永远叶子。
- **转换 PATCH**:正文→L2、L2→正文(子自动上提)、step↔node、`kind='step'` 时 `heading_level` 强制 null 的 invariant 拒绝。
- **严格 round-trip**:单段 / 多段 rich body,`heading_level` 来回切 body 字节级不变(替代旧 `test_roundtrip_2_explicitly_breaks`,新断言**两条路径都严格相等**)。
- **reorder**:移动子树区间计算、sort_order 落库。
- **invariants**:`_invariants.py` 三条新不变量。
- **导入**:parser 扁平 list → node 行,heading_level 正确。

### 10.2 前端

- `NodeTreePanel` 派生树渲染(给定扁平 list + heading_level → 正确缩进/父子)。
- 4 条输入路径:chip 改级、键盘 `Cmd+N`/`Tab`、多选 batch、markdown 行首(各 1 个 happy path)。
- 移除 `layerMark.spec.ts` / `procedureEditor.applyLayerRoles.spec.ts`。

---

## §11 风险与缓解

| 风险 | 缓解 |
|---|---|
| outliner 语义("改一行影响派生子")对 SOP 用户陌生 | inline chip + 即时树重排让因果可见;降级"子上提"是可预测的单一行为 |
| 不存 parent_id,大 procedure 每次读都 O(n) 派生 | O(n) 栈扫极快;必要时缓存派生结果,按 revision 失效 |
| 移动子树的 sort_order 区间计算前端算错 | 后端 dumb 落库但加一致性校验(同 procedure sort_order 唯一);前端单测覆盖区间边界 |
| 一次性重建波及 PDF/sign-off/numbering 多处读取 | §7 逐模块清单;分阶段实施(§12)每阶段跑全测 |
| `mark_service`/`batchMark` 误删 | §6.4 明确不随层级模式删,仅改读取口径,实施时单独确认 |
| heading 多段 body 在树里只显第一段,其余"藏"在 detail | 接受(Q1 决策);编辑器后续可加"回车拆行"nicety |

---

## §12 实施顺序(供 writing-plans 参考)

1. **后端模型 + 不变量**:`ProcedureNode` model、`_invariants.py` 三条、Alembic revision、`seed.py` 重写、重建 dev.db。
2. **树派生**:`node_tree.py`(`build_tree`)+ 单测;删 `layer_walk.py`。
3. **后端 API**:`GET /nodes`(含派生)、`PATCH /nodes/{id}`、`POST/DELETE/reorder/:batch`;删 `layer_apply_service` + 端点 + 测试。`numbering_service` 适配。
4. **Parser**:`ParsedNode.heading_level`、`structurer` 产扁平 list、`import_service` 落 node 行 + 单测。
5. **下游适配**:PDF、sign-off、version、attachment 读取口径(§7)+ 回归测试。
6. **前端**:`NodeTreePanel` + `NodeDetailPanel`、4 条输入路径、删 layerMark 全家桶 + spec。
7. **清理**:删作废 spec、`chapter_service`;手动 dev 验证(`running-smartsop-dev`);更新 memory(记一条"统一节点模型取代三分制",标记 `pdf-content-no-title`/`mark-mode-chapter-container`/`layer-overlay-q25-dryrun-gap` 等层级模式相关 memory 为 superseded)。

每阶段跑全测(`backend/.venv/bin/python -m pytest` + 前端 vitest),绿了再进下一阶段(memory `uv-missing-use-venv-python`)。

---

## §13 验收标准

1. 导入一个 parser 漏识别二级标题的 Word:在普通编辑里点该行 level chip 选 L2,即刻成为 L2 章节,标题就是该段文本,无残留、无"未命名章节"、无 apply 步骤。
2. 给一个 L2 章节(含若干正文子)选"正文":章节降为正文,原子节点自动上提到上一级章节;再选回 L2,子节点归位,body 字节级不变。
3. 多选 5 行正文 → 浮动条设 L3:一次生效。
4. 跳级(L1 直接 L3):允许编辑,发布检查清单出软警告。
5. step 节点尝试设 `heading_level`:被 invariant 拒绝。
6. PDF 渲染、编号、sign-off 在新模型下正确。
7. `layer_apply_service` / `layerMark.ts` / `ProcedureChapter` 已删,全测通过;新增严格 round-trip 测试(两条路径都相等)通过。

---

## §14 被本设计取代的前序工作

- `2026-05-28-content-chapter-roundtrip-design.md` — auto-extract/flatten 不再需要(本设计 §3.3 严格 round-trip 取代)。
- `2026-05-27-layer-overlay-auto-nest-design.md`、`2026-05-24-flat-layer-marking-design.md`、`2026-05-25-p2c-layer-marking-design.md` — 层级标定模式整体删除。
- memory `mark-mode-chapter-container`、`layer-overlay-q25-dryrun-gap`、`pdf-content-no-title`、`editor-route-reuse-no-reload` — 实施收尾时复核并标记 superseded/更新。
