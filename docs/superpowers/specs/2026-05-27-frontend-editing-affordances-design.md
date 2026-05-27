# 前端编辑能力增强（融合式标题等结构后处理）设计

**日期：** 2026-05-27
**状态：** 已确认（brainstorm 完成 / 待 writing-plans）
**作者：** 协作设计（cui_yuming + Claude）
**前序工作：** [`2026-05-27-word-parser-polish-design.md`](2026-05-27-word-parser-polish-design.md) / [`parser-comprehensive-evaluation.md`](../../parser-comprehensive-evaluation.md) §3.5（L2-1 永久否决记录）

## 背景

Word 解析器打磨闭环（2026-05-27 完成）确立了 **parser 是"忠实表达者"非"编辑者"** 原则（[`word-parser-solution.md`](../../word-parser-solution.md) §6.1）：原 docx 1 个 `<w:p>` ↔ IR 1 个 Block ↔ ParsedNode 1 个节点；不允许 parser 切融合段、合并、自动重排。

但综合评估发现：~30 mainline + ~150 Tier 3 共约 **180 个"融合式" chapter** —— 原 docx 一个段落里同时包含"号+短标题+长正文"（如 `3.1质量部是记录的归口管理部门，负责组织全公司记录表格的编制和校审。`）。当前 parser 把整段作为 chapter title（符合不变量），但 UX 上：

- 树标题被截断只显示前几个字
- 内容 sub-tree 是空的（用户期望"标题 + 内容"分离）
- PDF 渲染换行不优

解决路径是 **UI 端用户主导的结构后处理**，不动 parser、不动 ParseResult、不动 Word 重导入。

## 目标

1. **降低融合式 chapter 的 UX 摩擦**：用户能 1-2 步完成"长标题转内容 / 拆 heading + content"，从当前的"右键转 step / 转 content / 复制粘贴正文"≥5 步降到 1-2 步
2. **保留"决策权归用户"**：所有重组都由用户显式触发，零自动检测
3. **不动 parser 与解析数据模型**：后端 ParseResult 与 schema 形态不变；只新增"结构后处理"endpoint
4. **事务原子性**：转换/拆分类操作单 DB transaction，避免中间态

## 非目标

- ❌ Parser / Normalizer / Structurer 任何改动
- ❌ ParseResult schema 变更（`detected_patterns` 字段保留但仍不接入 UI，本 spec 不消费）
- ❌ 自动拆分 / 自动检测拆点 / 自动批量重组
- ❌ Undo 栈架构重写（沿用现有 store 快照机制）
- ❌ PDF 渲染折行优化（独立子系统）
- ❌ 多人协作冲突的高级合并语义（保留现有乐观锁 + 409 提示行为）

## 范围

**实施三件套 P1（A → B → C 顺序）**：

| 子项 | 摘要 | 改动面 |
|---|---|---|
| A | 树行标题 tooltip（chapter only，长度阈值触发） | 纯前端，1 文件 |
| B | "章节转内容"⋮ 菜单项 + 新原子 endpoint | 前端 store + 后端 1 router + 1 service |
| C | 详情面板"在光标处拆为标题+内容"按钮 + 新原子 endpoint | 前端 ChapterDetailPanel + store + 后端 1 router + 1 service |

---

## §1 架构与范围

### 1.1 系统边界

**前端 changes**：
- `frontend/src/components/editor/TreeRow.vue` — 标题 tooltip 包裹 + 新菜单项
- `frontend/src/components/editor/ChapterDetailPanel.vue` — 新按钮 + 光标跟踪
- `frontend/src/store/procedureEditor.ts` — 两个新 action + 本地 mutation 助手
- `frontend/src/api/chapters.ts` — 两个新 endpoint 包装
- `frontend/src/utils/editor.ts` — 导出 `TITLE_TOOLTIP_THRESHOLD` 常量

**后端 changes**：
- `backend/app/api/chapters.py` — 两个新 router 函数
- `backend/app/services/chapter_service.py`（或现有结构对应位置）— 两个新 service 函数
- `backend/app/schemas/chapter.py`（或 dto 模块）— 新 request/response 模型

**明确不动**：
- `backend/app/parser/` 整个目录
- `backend/app/schemas/parse.py`
- `frontend/src/types/parse.ts`
- 任何 docx 重解析路径

### 1.2 数据模型不变

`chapter` 表与 `step` 表 schema 零变更。新操作只是已有列的复合更新：
- B = DELETE chapter + INSERT step(kind=content) + 同级 reindex
- C = UPDATE chapter.title + INSERT step(kind=content) + chapter 下首位插入

### 1.3 关键不变量

1. **顺序保真**（spec §6）：B 后新 content 占原 chapter sort_order；C 后新 content 在 chapter 下首子位
2. **决策权归用户**：拆点必须由用户光标显式给出，绝无自动推断
3. **事务原子性**：B/C 各自一次 DB transaction，失败回滚到调用前

### 1.4 实施顺序与独立性

**A → B → C**，每段独立 commit、独立测试、可独立部署：
- A 纯渲染层，不依赖 B/C
- B 与 C 独立（不同 endpoint、不同前端入口）；但因后端 service 共用 helper（reindex / version check），实施时建议先 B 再 C
- C 多一层光标位置传递与焦点切换

---

## §2 A — 树行 tooltip

### 2.1 触发条件

- 仅 `row.kind === 'chapter'` 的行挂 tooltip（content / step 标题短，且 step 已有 form_type 副信息）
- `el-tooltip.disabled` 绑定 `displayTitle.length <= TITLE_TOOLTIP_THRESHOLD`，短标题不弹

### 2.2 阈值与显示

- `TITLE_TOOLTIP_THRESHOLD = 30`（CJK 字符）— 30 字之内的标题在树列宽 240-360px 区间基本不省略
- 显示内容：`displayTitle`（即 `row.title || row.fallback`）
- `placement="top-start"` 与左侧编号对齐，光标不挡
- `show-after="300"` 防误触
- 弹层最大宽 `400px` + 自动换行

### 2.3 实现

**文件**：`frontend/src/components/editor/TreeRow.vue`

模板包裹 `.tr-title`：
```html
<el-tooltip
  :content="display"
  :disabled="display.length <= TITLE_TOOLTIP_THRESHOLD || row.kind !== 'chapter'"
  placement="top-start"
  :show-after="300"
  popper-class="tr-title-tooltip"
>
  <span class="tr-title" :class="{ 'tr-title--fallback': titleFallback }">{{ display }}</span>
</el-tooltip>
```

`TITLE_TOOLTIP_THRESHOLD` 从 `@/utils/editor` 导入。

样式 `tr-title-tooltip` 加 `max-width: 400px; white-space: normal; word-break: break-word;`。

### 2.4 测试

**文件**：`frontend/tests/unit/components/editor/TreeRow.spec.ts`（沿用现有命名）

测试用例：
1. `title.length === 30` 的 chapter 行 → `el-tooltip` 的 `disabled` prop = true
2. `title.length === 31` 的 chapter 行 → `disabled` = false
3. `kind === 'content'` 的长标题 → `disabled` = true（非 chapter 不弹）
4. 不验证 popper 真实 DOM（jsdom 限制；参考 [[el-dropdown-jsdom-test]] 教训），只验证 `disabled` prop 与 wrapper 结构

---

## §3 B — 章节转内容（chapter→content）

### 3.1 端到端数据流

```
TreeRow ⋮ 菜单
  └─ '转为内容块' 项（disabled when has-children OR is-root）
      └─ emit('convert', 'chapter-to-content')
          └─ store.convertChapterToContent(id)
              ├─ const map = await this.ensureSaved()   # 临时节点先落盘，返回 idMap
              ├─ POST /chapters/:realId/convert-to-content
              ├─ 响应：{ new_step_id, parent_chapter_id, sort_order }
              ├─ 本地 patch：删 chapter + 在 parent 下插入 step
              ├─ pushUndo(`chapter-to-content:${realId}`)   # 沿用现有快照机制
              └─ selectNode(new_step_id)                # 焦点切到新 content
```

### 3.2 后端 endpoint

**Router**：`POST /api/chapters/{chapter_id}/convert-to-content`

**Request body**：空（`{}`）

**Response 200**：复用 `ConversionResult`（已有 schema）
```json
{
  "created": ["new_step_uuid"],
  "deleted": ["chapter_uuid"]
}
```

**Service 语义**（单 DB transaction，沿用 `conversion_service.convert_to_step` 模式）：
1. `_get_chapter` 取 chapter；`_get_proc_editable` 取程序（校验非只读）
2. 校验 chapter 无任何 child chapter / child step → 否则 `400 CHAPTER_HAS_CHILDREN`
3. 校验同级 siblings 不会因转换混合类型（`_other_chapter_children_count(parent_id, exclude=id) == 0`）→ 否则 `400 SIBLING_TYPE_CONFLICT`（与 `convert_to_step` Q25 互斥规则一致；天然覆盖"根 chapter 周围还有其他 chapter"场景）
4. 创建新 step：
   - `kind = 'content'`
   - `content = chapter.title`（原标题搬运为 content 文本；保留 HTML）
   - `title = ''`
   - `sort_order = 0`（与 `convert_to_step` 一致；numbering_service.recompute 后会重排）
   - `chapter_id = chapter.parent_id`
   - `input_schema = {}`
5. `chapter.is_active = False` + `chapter.deleted_at = utcnow()`（软删，与现有模式一致）
6. `numbering_service.recompute(db, proc.id)` + `optimistic_lock.bump(proc)` + `db.flush()`
7. `audit_service.log_procedure_action` action="chapter-to-content"
8. 返回 `ConversionResult(created=[new_step_id], deleted=[chapter_id])`

**事务**：service 函数全包；任一步失败回滚。

**乐观锁**：`optimistic_lock.bump(proc)` 在 numbering recompute 后调用，与 `convert_to_step` 一致；版本冲突由 `_get_proc_editable` 的只读检查兜底（草稿只有一个，多人协作场景的细化留给现有冲突处理机制）。

### 3.3 前端 store action

```ts
async convertChapterToContent(id: string): Promise<void> {
  const map = await this.ensureSaved()
  const realId = map[id] ?? id
  const result = await convertChapterToContentApi(realId)
  // 沿用 convertToStep 模式：结构变更后整段刷新（保险），避免本地手工 mutation 偏差
  await this.refreshAfterConversion(result)
  this.pushUndo(`chapter-to-content:${realId}`)
  this.selectNode(result.created[0])
}
```

`refreshAfterConversion(result)` 是 store 内现有 / 新加的助手 —— 沿用 `convertToStep` 的模式：成功后整段 refetch procedure。理由：结构变更涉及 numbering recompute + procedure version bump，本地 patch 易漂移；refetch 一致性更稳。（与 spec §3.1 "本地 patch"的初版相比微调；spec 实施时按此现网行为执行）

### 3.4 菜单项与禁用规则

`TreeRow.vue` 的 `⋮` `<el-dropdown-menu>` 新增（在现有 `to-step` / `to-content` 之后）：

```html
<el-dropdown-item
  v-if="row.kind === 'chapter'"
  command="chapter-to-content"
  :disabled="row.has_children"
  :title="row.has_children ? '请先处理子节点后再转换' : ''"
>
  转为内容块
</el-dropdown-item>
```

**命令字符串决策**：用 `chapter-to-content`（不复用现有 `to-content` —— 后者已用于 step→content）。`onMore` 函数扩展 command 类型联合：`'to-step' | 'to-content' | 'chapter-to-content' | 'remove'`。

**禁用条件**：仅 `has_children`。根 chapter 不需要前端额外禁用 —— 后端 `SIBLING_TYPE_CONFLICT` 校验会拒绝有同级 chapter 的情况；单根 chapter 转 content 是合法操作（procedure 可只剩 content 块，与现有 `convert-to-step` 行为一致）。

### 3.5 错误处理

| HTTP | 后端错误码 | 前端响应 |
|---|---|---|
| 400 | `CHAPTER_HAS_CHILDREN` | `ElMessage.warning('该章节下有子节点，请先处理')` + noop（UI 本应已禁用） |
| 400 | `SIBLING_TYPE_CONFLICT` | `ElMessage.warning('同级仍有章节，转换会违反类型互斥规则')` + noop |
| 400 | `PROCEDURE_READONLY` | `ElMessage.warning('当前版本只读，无法编辑')` + noop |
| 5xx | — | `ElMessage.error('转换失败，请稍后重试')` + 强制 refresh |

### 3.6 测试

**后端**（追加到 `backend/tests/unit/services/test_conversion_service.py`，沿用现有 `Factory` 与 `META` 模式）：
1. Happy path：唯一 chapter 无 children → 转换后 chapter is_active=False，新 step kind=content，content=原 title
2. 有 child chapter → 400 `CHAPTER_HAS_CHILDREN`
3. 有 child step → 400 `CHAPTER_HAS_CHILDREN`
4. 同级有其他 chapter → 400 `SIBLING_TYPE_CONFLICT`
5. 程序只读（非 DRAFT）→ 400 `PROCEDURE_READONLY`
6. 转换后 numbering 重算 + procedure revision bump 生效

**前端 `frontend/tests/unit/store/procedureEditor.spec.ts`**：
- `convertChapterToContent` 调用前后 `chapters[]` / `steps[]` 状态变化
- `selectNode` 落到新 step
- `undo()` 一次能还原到调用前

**前端 `frontend/tests/unit/components/editor/TreeRow.spec.ts`**：
- `has_children=true` 时菜单项 `disabled=true`
- `is_root=true` 时菜单项 `disabled=true`
- 非 chapter kind 时菜单项不出现

---

## §4 C — 在光标处拆 heading + content

### 4.1 端到端交互

`ChapterDetailPanel.vue` 标题 textarea 下方新增按钮：

```
┌─ 章节标题 ───────────────────────────────────┐
│ [el-input textarea autosize]                  │
│  3.1质量部是记录的归口管理部门，负责组织全公司 │
│  记录表格的编制和校审。                       │
└───────────────────────────────────────────────┘
[💡 在光标处拆为标题+内容]    跳号 [○]
```

**用户操作流**：
1. 点进 textarea → 把光标放到拟拆点（如 "门，" 后，offset=15）
2. 点按钮 → `store.splitChapterTitleContent(chapter.id, cursorOffset)`
3. 响应回来：原 chapter.title 截短到 offset 处；同 chapter 下首位插入新 content，content=offset 之后的文本
4. 焦点切到新 content（左侧树选中、右侧 panel 切到 ContentDetailPanel）

### 4.2 光标位置获取

```ts
const titleInputRef = ref<{ textarea: HTMLTextAreaElement } | null>(null)
const cursorOffset = ref<number | null>(null)

function refreshCursor(): void {
  const el = titleInputRef.value?.textarea
  cursorOffset.value = el ? el.selectionStart : null
}
```

`el-input` 实例（type=textarea）暴露 `.textarea` ref。在 textarea 的 `focus` / `input` / `select` / `mouseup` / `keyup` 事件触发 `refreshCursor()`。

**为何用 `selectionStart` 而非 selectionEnd**：若用户选中一段（end > start），按"拆"按钮我们用 start 作为拆点，**忽略选中范围**（不删除选中内容）。

### 4.3 按钮启用规则

按钮 `disabled` 当且仅当下列任一为真：
- `!store.editable`（只读模式）
- `cursorOffset === null`（textarea 未聚焦 / 未获取光标位）
- `cursorOffset === 0`（拆点在头 → 空标题）
- `cursorOffset >= chapter.title.length`（拆点在尾 → 空 content）
- `chapter.title.trim() === ''`（空标题）

实现为 computed `splitDisabled`。

### 4.4 后端 endpoint

**Router**：`POST /api/chapters/{chapter_id}/split-title-content`

**Request body**：
```json
{ "cursor_offset": 15 }
```

**Response 200**：复用 `ConversionResult`（不增新 schema）
```json
{
  "created": ["new_step_uuid"],
  "deleted": []
}
```

> 拆分操作语义上"创建一个新 step"，原 chapter 仍存在（只是 title 截短）；故 `deleted` 为空。前端从 `created[0]` 拿新 step.id 选中焦点；新 step 的 sort_order 永远是 0（拆后 chapter 下首位），其他 step 已 +1。

**Service 语义**（单 DB transaction，沿用 `conversion_service` 模式）：
1. `_get_chapter` 取 chapter；`_get_proc_editable` 取程序
2. 校验 `0 < cursor_offset < len(chapter.title)` → 否则 `400 INVALID_CURSOR`
3. 校验 `chapter.title[cursor_offset:].strip() != ''` → 否则 `400 EMPTY_CONTENT`
4. `new_title = chapter.title[:cursor_offset]`（**保留尾部标点，不剪不补** —— 光标位代表用户意图）
5. `new_content_text = chapter.title[cursor_offset:]`
6. `chapter.title = new_title`
7. 把当前 chapter 下所有现有 step 的 sort_order 全部 +1（让出 0 位）
8. 创建新 step：`chapter_id=:id, kind='content', content=new_content_text, title='', sort_order=0, input_schema={}`
9. `numbering_service.recompute(db, proc.id)` + `optimistic_lock.bump(proc)` + `db.flush()`
10. `audit_service.log_procedure_action` action="split-title-content"
11. 返回 `ConversionResult(created=[new_step_id], deleted=[])`

**事务**：service 函数全包；任一步失败回滚。

**幂等性说明**：**不幂等** — 重复 POST 会再拆一次。前端 store 用 in-flight lock 防双击。

**版本号**：乐观锁 → `409 CONFLICT_VERSION`。

### 4.5 前端 store action

```ts
// inflightSplit 是新增的 store state field: Set<string>
async splitChapterTitleContent(id: string, cursorOffset: number): Promise<void> {
  const map = await this.ensureSaved()
  const realId = map[id] ?? id
  if (this.inflightSplit.has(realId)) return  // 双击防护
  this.inflightSplit.add(realId)
  try {
    const result = await splitChapterTitleContentApi(realId, { cursor_offset: cursorOffset })
    await this.refreshAfterConversion(result)
    this.pushUndo(`split-title-content:${realId}`)
    this.selectNode(result.created[0])
  } finally {
    this.inflightSplit.delete(realId)
  }
}
```

成功后整段 refetch（同 §3.3 决策），不手工 patch 本地数组。

### 4.6 边界保护汇总

| 场景 | 行为 |
|---|---|
| cursor=0 | 前端按钮 disabled；若绕过仍 POST → 后端 422 |
| cursor>=len | 前端 disabled；后端 422 |
| 选中段（start<end） | 仅用 start，不删除选中 |
| 空标题 | 按钮 disabled |
| 只读模式 | 按钮 disabled |
| 双击按钮 | store inflight lock 拦截第二次 |
| 拆后 content 为空白 | 后端 422 拒绝 |
| chapter 已有子 chapter | **允许拆** — 拆操作只往 chapter 下加 leaf content，子 chapter 结构不受影响（与 B 不同：B 整体降级所以禁子节点；C 只加叶子） |
| 用户改标题后立即点拆 | textarea blur 前 `onTitle` 防抖未 flush 时，点按钮先 `await onTitle.flush()` 确保后端拿到的 title 与 cursor 一致 |

### 4.7 测试

**后端**（追加到 `backend/tests/unit/services/test_conversion_service.py`）：
1. Happy path：cursor=15 → chapter.title 截短到 15 + 新 content step kind=content + sort_order=0
2. `cursor=0` → 400 `INVALID_CURSOR`
3. `cursor=len(title)` → 400 `INVALID_CURSOR`
4. 拆出 content 为全空白 → 400 `EMPTY_CONTENT`
5. chapter 已有 N 个 step children：新 step sort_order=0，其余 step sort_order 全部 +1
6. chapter 有子 chapter：不报错，子 chapter 不受影响
7. 程序只读 → 400 `PROCEDURE_READONLY`

**前端 `frontend/tests/unit/components/editor/ChapterDetailPanel.spec.ts`**：
- 渲染按钮；cursor=null 时 disabled；cursor=15 时 enabled
- cursor=0 / cursor=title.length 时 disabled
- 只读模式按钮 disabled
- 点击按钮触发 `store.splitChapterTitleContent` 携带正确 cursor

**前端 `frontend/tests/unit/store/procedureEditor.spec.ts`**：
- `splitChapterTitleContent` 调用前后 chapter.title 截短 + steps[] 多一项
- 焦点切换到新 content
- `undo()` 一次完整还原
- 双击只调 1 次 API（inflight 拦截）

---

## §5 Undo & 数据一致性

### 5.1 Undo 沿用现有快照机制

`store/procedureEditor.ts` 已有 `pushUndo()` / `undo()`，本 spec **不引入新 undo 架构**，只在 B/C 两个新 action 末尾调用 `pushUndo()`。

- B 的 `convertChapterToContent` 整个调用作为**一个 undo step**
- C 的 `splitChapterTitleContent` 同上

### 5.2 本地 undo 与后端落盘的一致性约定

现有 store undo 是**纯前端 state restore**，不会反向调后端 endpoint。这意味着：

- 用户在 B/C 后点 undo → 前端视图回到操作前；后端实际仍是操作后状态
- 用户后续保存（或刷新页）→ 前端视图会重写到后端，实际等价于"反向操作已落盘"

这与现有 `convertChapterToStep` / `convertStepToChapter` 的 undo 行为一致，**本 spec 不重写**。

**UX 提示**：B/C 操作成功时 `ElMessage.success` 提示"已转换 / 已拆分"；不主动提示"撤销将不刷新后端"（与现有行为对齐，避免提示噪声）。

### 5.3 失败回滚

**后端**：单 transaction，DB 层自动回滚。Service 内不需要手动 try/except wrap。

**前端**：
- API 调用失败 → 不调用 `applyXxx` mutation → 不调用 `pushUndo` → 本地状态零变更
- API 200 但本地 mutation 抛异常（理论不应发生）→ try/catch + 强制 `procedureEditor.refresh()`

### 5.4 数据一致性边界

| 场景 | 风险 | 处理 |
|---|---|---|
| B 调用过程中网络断 | 后端可能已 DELETE chapter 但响应没回 | catch → `ElMessage.error` → 强制 refresh |
| C 调用过程中网络断 | 同上 | 同上 |
| 用户编辑标题同时点拆按钮 | cursor 与最新 title 不匹配 | 点按钮先 `await onTitle.flush()`（§4.6 已列） |
| 多 tab / 协作并发 | 版本号冲突 | 后端乐观锁 → 409 → 前端 refresh |

### 5.5 顺序保真校验

B/C 引入后，flat row 拓扑由用户操作改写（合法），但要保证：
- B 后：新 content 在 parent 下出现在原 chapter 索引处
- C 后：新 content 在 chapter 下首子位

**单测**断言（在 §3.6 / §4.7 已隐含包含；spec 实施时 plan 阶段写明 assertion）。

### 5.6 观测

后端 service 添加 INFO 日志：
```python
logger.info("chapter.convert_to_content id=%s parent=%s sort=%s", id, parent_id, sort_order)
logger.info("chapter.split_title_content id=%s cursor=%s new_step=%s", id, cursor, new_step_id)
```

便于事后排查"我章节没了"或"拆没生效"类反馈。

---

## §6 实施顺序与里程碑

| 阶段 | 子项 | 估时 | 验收 |
|---|---|---|---|
| M1 | A 树行 tooltip | 0.5 d | 前端单测通过；浏览器实测长 chapter 行 hover 出 tooltip |
| M2 | B 后端 endpoint + service + 单测 | 1 d | 6 个后端单测通过 |
| M3 | B 前端 store + TreeRow 菜单 + 单测 | 0.5 d | 前端单测通过；浏览器实测无 children 的 chapter 转 content 成功 |
| M4 | C 后端 endpoint + service + 单测 | 1 d | 7 个后端单测通过 |
| M5 | C 前端 ChapterDetailPanel + store + 单测 | 1 d | 前端单测通过；浏览器实测光标位拆分成功 + undo 还原 |
| M6 | 浏览器端 MCP 验收（实样本 36 份） | 0.5 d | 抽 5 份融合式 chapter 演示完整 A+B+C 流程并截图存档 |

**总计 ~4.5 d**（写 plan 时会按 bite-size 步骤细化）。

每阶段一独立 commit；M1-M5 各自可单独部署（前端/后端可分别 merge）；M6 是验收闭环不产出 commit。

---

## §7 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 后端新 endpoint 与现有 reindex helper 不兼容 | service 写错导致 sort_order 错乱 | 单测覆盖 sort_order 重排（§3.6 case 6 / §4.7 case 5） |
| 前端 store mutation 与 refetch 不一致 | UI 状态与后端实际不一致 | 失败路径强制 refresh；M6 浏览器实测验证 |
| `el-input` 的 textarea ref 在 EP 版本间不一致 | cursor 获取失败 | spec 实施时 plan 阶段验证 EP 当前版本的 ref 字段名（`input` vs `textarea`），fallback 用 `document.activeElement` |
| 用户对 chapter→content 的"标题保留为 content"语义不直观 | 用户报"我标题哪去了" | 操作后 `ElMessage.success` 含明确文案"已将章节标题转为内容块"；无需弹 confirm dialog |
| 双击 / 抖动 / 误点 | 多次拆同一段 | inflight lock（§4.5）+ 单测 case 8 |
| `detected_patterns` 字段长期不消费 | 后端继续输出但前端无人用 = 死代码 | 保留，因后续 P2 批量重组（未来 spec）会用到；本 spec 不删 |

---

## §8 不变量回顾（终稿）

实施本 spec 后必须仍然成立的不变量：

1. **Parser 不改原结构**（[`word-parser-solution.md`](../../word-parser-solution.md) §6.1 + 持久 memory `parser-no-mutation-principle`）：parser 路径零改动 ✅
2. **顺序保真**（[`word-parser-solution.md`](../../word-parser-solution.md) §6）：B/C 产物在原索引处 ✅
3. **决策权归用户**（§C.0 人机分工）：B/C 均显式触发，零自动 ✅
4. **数据模型稳定**：chapter / step 表 schema 零变更 ✅
5. **ParseResult schema 稳定**：`detected_patterns` 字段保留但不消费 ✅

---

## §9 下一步

1. 本 spec → writing-plans skill：产出 `docs/superpowers/plans/2026-05-27-frontend-editing-affordances-eval.md`（bite-size 任务清单 + TDD 步骤）
2. plan 评审 → 实施（subagent-driven 或 inline 由用户选）
3. M6 完成后 → finishing-a-development-branch
