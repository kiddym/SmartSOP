# 层级标定「动态挂载」(auto-nest) 设计

**日期:** 2026-05-27
**状态:** 已确认 (brainstorm 完成 / 待 writing-plans)
**作者:** 协作设计 (cui_yuming + Claude)
**前序工作:**
- [`2026-05-24-flat-layer-marking-design.md`](2026-05-24-flat-layer-marking-design.md) — Word 导入弹窗内的「层级标定」交互模型(本设计借用同名概念,作用于已入库 procedure 的编辑器)
- memory `layer-overlay-q25-dryrun-gap` — 现状校验器为何按 `originalParent` 分组(本期反向调整)

## 背景

编辑器有「层级标定」模式(`ChapterTreePanel.vue:460-466`):用户给文档序里的每行选 `保持 / 一级 / 二级 / 三级`,点「应用层级」一次性批改章节层级。前端 walk(`layerMark.ts:computeLayerUpdates`)已能算出:
- 每个被升的叶子最终应落到哪个父节点之下、夹到第几级;
- 后续 `保持` 的叶子应**重挂(`leaf-reparent`)** 到最近的标题之下。

**但落地链条是断的**:
1. 后端 `POST /steps/{id}/convert-to-chapter` 单行 API 内置了 §Q25 拦截 (`conversion_service.py:319`,父下还有任何叶子兄弟即拒绝)。批量升级时第一行就被拒。
2. 前端 `applyLayerRoles` 也根本不消费 walk 产出的 `leaf-reparent` 操作 (`procedureEditor.ts:910` 注释:「leaf-reparent 由 reload 后基于 chapter 重排自然形成」—— 但 chapter_id 在 DB 实际并未变,所以"自然形成"从未发生过)。
3. 前端 `validateLayerQ25` 因此被刻意对齐成"按 `originalParent` 分组"以**正确反映后端不会重挂**的事实(`layerMark.ts:130-143`),从而在 dry-run 阶段就拦下用户。

结果是:用户在 UI 上看到的"下方内容自动缩进到新章节下"只是 `computeLayerIndents` 给的视觉预览;一旦点应用,要么被 Q25 banner 拦下,要么(如果手工把 Q25 绕开)后端拒绝。这是个**半成品功能**——walk 早就替"动态挂载"做好了规划,但 apply 端没接住。

## 目标

1. **完成"动态挂载"语义**:用户给某行选「二级/三级」时,该行下方至"下一个被升的兄弟"之间的所有叶子(content/step)**自动**重挂为新章节的子节点。
2. **应用为单事务**:多行升级 + 重挂 + 章节重排 + chapter→content 一次提交;任一失败全部回滚,不留半成品。
3. **前后端 walk 等价**:前端 walk 仍是 spec 与预览/dry-run 来源;后端独立 walk 实现并以同一份 fixture 锁住。
4. **校验器恢复"按理想末态"分组**:`validateLayerQ25` 改为按 walk 的 `u.parent_id` 分组,因为后端拓扑现在 = walk 末态。

## 非目标

- ❌ ContentDetailPanel 加"升章节"按钮(memory `word-parse-audit-2026-05-27` 的 🟡 项,与本期解耦)
- ❌ 反向"动态拆出":chapter 降为 content 时把其子叶子提到父级(罕用且 Q25 会拦)
- ❌ 拖拽式批量升 / 键盘快捷键(layer 模式现有 radio 已足够)
- ❌ 删除 `POST /steps/{id}/convert-to-chapter` 单行 API(保留,未来 ContentDetailPanel 升章节按钮等场景可能复用)
- ❌ 调整 `+新增 ▾` / 行级 `:` 菜单在 layer 模式下的可见性(保持现状)
- ❌ Undo 栈架构重写(沿用现有 `pushUndo('layer')` 浅快照;若新事务后 undo 行为不可接受,则降级为 toast 提示"层级应用不可撤销",而非重做栈)

## 范围

**实施 P1(单次实施,不分子项)**:

| 模块 | 摘要 | 改动面 |
|---|---|---|
| 后端 | 新增 `layer_apply_service` + `POST /procedures/{id}/apply-layer-roles` 事务性端点 | 1 service 新增 / 1 router 新增 / 2 schema 新增 |
| 前端 store | 重写 `applyLayerRoles`:单次后端调用,移除分两步的 in-memory mutate + per-row API | `procedureEditor.ts:867` |
| 前端校验器 | `validateLayerQ25` 改为按 `u.parent_id` 分组,删除 `LayerRow.originalParent` 字段及注释 | `layerMark.ts:144-187` + `layerMark.ts:9-12` |
| 前端 API | 新增 `applyLayerRoles` client | `frontend/src/api/procedures.ts` |
| Memory | `layer-overlay-q25-dryrun-gap.md` 加 SUPERSEDED 标记或删除 | `~/.claude/.../memory/` |

---

## §1 语义规范

### 1.1 用户故事

进入「层级标定」模式 → 给若干叶子(content/step)标 `一级/二级/三级` → 点「应用层级」。后端事务性地完成:
- 标了角色的叶子升为新章节;
- **每个新章节自动收养** "下方直到下一个被升的兄弟(任何级别)"之间的所有叶子作为子节点;
- 同 batch 内章节的 reorder / chapter→content 一并完成;
- 任一失败回滚,不留半成品。

### 1.2 收养规则

在文档序里遍历:
- **被升行 X 的收养块** = `[X 之后, 下一个"会更新 heading 上下文"的行之前)` 区间内所有 `保持` 的叶子。
- "会更新 heading 上下文"的行 = 任何变成 chapter 的行,即 `role ∈ {chapter_1, chapter_2, chapter_3}`(无论该行原本是叶子还是已有章节)。**`role=content` 的章节(章节→内容)不构成收养边界**(walk 不更新 l1/l2/l3),其后续叶子仍归属再之前那个 heading。
- 收养块内元素**保持自身顺序**,以 sort_order 0..N-1 排在新章节下。
- 不再递归剥洋葱: walk 已确保 L3 在 L2 之后会自动成为 L2 的子章节;L3 自己的收养块会被挂到 L3 之下。因此当 X 在 L2、Y 在 L3、Y 在 X 之后时:`[X, Y)` 的叶子挂到 X 下;`[Y, 下一个被升)` 的叶子挂到 Y 下;Y 本身作为 X 的子章节出现。

### 1.3 已有夹紧规则保持不变

`computeLayerUpdates` 的"祖先链夹紧"行为延续:
- `chapter_2` 无 L1 上下文 → 夹回 L1
- `chapter_3` 无 L2 上下文 → 夹到 L1
- 收养块跟着被夹后的级别走,不需要单独逻辑。

### 1.4 截图场景演示

输入(`3.0 职责` 下,均为 content):
```
3.0 职责 (L1)
  3.1 崔宇明                          ← roleMap: chapter_2
  负责编制本程序...                    ← keep
  全面负责公司的财务...                ← keep
  3.2 王覆宇                          ← roleMap: chapter_2
  全面负责公司产品的架构...            ← keep
  负责公司服务器...                    ← keep
  3.3 于星河                          ← roleMap: chapter_2
  全面负责公司产品的前端...            ← keep
  负责公司产品开发...                  ← keep
```

期望末态:
```
3.0 职责 (L1)
  3.1 崔宇明 (L2 章节)
    负责编制本程序...
    全面负责公司的财务...
  3.2 王覆宇 (L2 章节)
    全面负责公司产品的架构...
    负责公司服务器...
  3.3 于星河 (L2 章节)
    全面负责公司产品的前端...
    负责公司产品开发...
```

---

## §2 架构与数据流

### 2.1 现状 vs 新方案

```
当前 (3 步,链条断裂):
  applyLayerRoles()
    ├─ ensureSaved() 拿 idMap
    ├─ for 每个 to-chapter: POST /steps/{id}/convert-to-chapter  ❌ Q25 拒
    │   reload()
    └─ 章节 reorder / to-content: 本地 mutate → flush 走 PUT /procedures/{id}
       leaf-reparent: 计算但从未执行

新 (2 步,单事务):
  applyLayerRoles()
    ├─ ensureSaved() 拿 idMap
    └─ POST /procedures/{id}/apply-layer-roles
        body: { roles: {step_or_chapter_id: LayerRole}, lock_version: int }
        200 → { chapter_map: {temp_id: real_id}, new_lock_version: int }
        400 → { error_code, conflicts: [...] }
       reload()
```

### 2.2 关键设计选择

- **walk 逻辑搬到后端独立实现**:前端 walk 仍是 spec + 预览 + dry-run 来源;后端在 `layer_apply_service` 中独立实现同一算法。**双端必须等价**——通过共享单测 fixture (`tests/unit/.../layer-apply-fixtures.json`) + e2e 锁住。
- **不信任前端传的 rows**:后端只接收 `roles` map,内部从 DB 重建 LayerRow 列表,自己跑 walk。避免前端篡改/失同步导致的拓扑漂移。
- **保留单行 `convert-to-chapter` API**:layer apply 不再走它,但其他潜在调用方(`store.convertToChapter` 已无 UI 调用方但保留;未来 ContentDetailPanel 升章节按钮)仍可用。

### 2.3 新增/修改文件

| 文件 | 改动 |
|---|---|
| `backend/app/services/layer_apply_service.py` | **新增**: walk + apply 实现 |
| `backend/app/routers/procedures.py` | 新增 `POST /procedures/{id}/apply-layer-roles` 路由 |
| `backend/app/schemas/node.py` | 新增 `LayerApplyIn` / `LayerApplyOut` / `LayerConflictOut` |
| `frontend/src/api/procedures.ts` | 新增 `applyLayerRoles` API client |
| `frontend/src/store/procedureEditor.ts` | 重写 `applyLayerRoles` action (line 867);`layerRows` getter 中移除 `originalParent` 填充(line 257 + 267) |
| `frontend/src/utils/layerMark.ts` | `validateLayerQ25` 改分组逻辑;`LayerRow` 类型移除 `originalParent` 字段(line 11) |
| `backend/tests/unit/services/test_layer_apply_service.py` | **新增** |
| `frontend/tests/unit/utils/layerMark.test.ts` | 重写 Q25 验证测试 |
| `frontend/tests/unit/store/procedureEditor.test.ts` | applyLayerRoles 集成测试 |

---

## §3 后端实现详解

### 3.1 端点

```
POST /api/v1/procedures/{procedure_id}/apply-layer-roles
Content-Type: application/json
{
  "roles": { "<step_or_chapter_id>": "chapter_1" | "chapter_2" | "chapter_3" | "content" | "keep" },
  "lock_version": 42
}
```

未在 `roles` 中出现的节点视为 `keep`(章节)/ `keep`(叶子);后端不要求传完整 map。

**响应**:
```
200 OK
{ "chapter_map": { "<old_step_id>": "<new_chapter_id>" }, "new_lock_version": 43 }
  # chapter_map 仅含本 batch 的 leaf→new_chapter 映射(Phase A 产出);
  # 前端 reload 后理论用不上,作为可观察契约 + 调试方便保留

400 Bad Request
{ "error_code": "SIBLING_TYPE_CONFLICT",
  "conflicts": [{ "parent_id": "...", "chapter_children": [...], "leaf_children": [...] }] }
{ "error_code": "CHAPTER_DEPTH_EXCEEDED", "detail": "..." }
{ "error_code": "CHAPTER_HAS_CHILDREN", "chapter_id": "..." }
  # Phase C 兜底:用户给一个有子章节的 chapter 选了 content

409 Conflict
{ "error_code": "OPTIMISTIC_LOCK", "current_lock_version": 44 }
```

### 3.2 `layer_apply_service.apply_layer_roles(db, procedure_id, payload, meta)`

1. **加载 + 乐观锁**:取 procedure 行,比对 `lock_version`,不匹配 → 409。
2. **重建 LayerRow 列表**:按 DB 当前文档序(章节深度优先 + 叶子按 chapter_id 分组 + sort_order)生成 `LayerRow[]`。每行带 `id / kind / level / has_leaf_children / original_parent`。**忽略前端传的 rows,只用 roles map**。
3. **Walk**:执行与前端 `computeLayerUpdates` 完全等价的算法,产出 `dict[id, LayerUpdate]`。共享 fixture 锁住等价性。
4. **末态 Q25 校验**:按 walk 末态 `parent_id` 分组,任一组同时有 `chapter` 类 (`reorder` + `to-chapter`) 和 `leaf` 类 (`to-content` + `leaf-reparent`) → 400 `SIBLING_TYPE_CONFLICT`。
5. **深度校验**:任一 `to-chapter` 的 `level > MAX_DEPTH (3)` → 400 `CHAPTER_DEPTH_EXCEEDED`(walk 已夹紧,理论上不会超;作为防御保留)。
6. **执行(单事务)**:
   - **Phase A — `to-chapter`**(按文档序处理):
     - 解析 `u.parent_id`:walk 中 `l1/l2/l3` 跟踪的是 source row.id,因此 `u.parent_id` 可能指向**本 batch 中先一步被升的另一叶子**。维护 `leaf_id → new_chapter_id` map,创建当前章节时先查 map 决定真实 parent_id(若 map 命中则用新 chapter id,否则该 id 本就是现存 chapter id 或 null)。
     - 创建新 `ProcedureChapter`(`parent_id` 解析后、`level` 来自 walk、`title = step.title or "未命名章节"`、`sort_order = u.sort_order`)。
     - 原叶子的 rich body(经 `_compose_step_body(st)` = `st.content`)非空 → 在新章节下创建 `kind='content'` 子 step(`sort_order=0`、`title=""`、`content=body`、`input_schema={}`)。**沿用现有 `convert_to_chapter` 语义**:`input_schema / attachment_marks / skip_numbering` 等字段**不保留**(已是当前单行 API 的行为,此处不引入回归);如果用户对此有意见,另立项处理。
     - 原叶子软删 (`is_active=False, deleted_at=now`)。
     - 把 (leaf_id → new_chapter_id) 写入 map,供后续 Phase A/D 解析 parent_id 用。
   - **Phase B — `reorder`** (章节重排): UPDATE chapter.parent_id, sort_order, level。`u.parent_id` 不会指向本 batch 新建的章节(walk 不会把已有章节挂到新升的叶子下),无需 map 解析。
   - **Phase C — `to-content`** (章节→内容):
     - **前置校验**:被降的 chapter 必须无任何子节点(chapter 子或 leaf 子均不允许)。沿用 `convert_to_content` 的 `CHAPTER_HAS_CHILDREN` 错误码;若违反 → 400 整事务回滚。**注意**:当前前端 `effectiveRole` 仅按 `hasLeafChildren` 屏蔽 `content` 选项,未校验 chapter 子;后端在此兜底,前端可在后续迭代里同步加屏蔽(本期不做)。
     - 创建新 `kind='content'` step,`title=""`、`content = "<p>{escape_html(chapter.title)}</p>" if chapter.title.strip() else ""`(与 `procedureEditor.ts:918-925` in-memory 行为一致)、`chapter_id = resolve(u.parent_id)`(同 Phase D 的 map 解析)、`sort_order = u.sort_order`。
     - 软删原 chapter。
   - **Phase D — `leaf-reparent`**: UPDATE step.chapter_id = resolve(u.parent_id);其中 `resolve(p)` = "若 p 命中 Phase A 的 leaf_id→new_chapter_id map 则替换为对应新 chapter id,否则原样使用"。sort_order 按 walk 给的值。
   - **执行顺序**:必须按 A → B/C/D 的顺序;A 内部按文档序处理(以构建 map 时不出现"未来引用");B/C/D 之间无依赖,但都依赖 A 的 map。
7. **重算 + 锁**:`numbering_service.recompute(db, procedure_id)` + `optimistic_lock.bump(proc)`。
8. **审计**:写入一条 action=`apply-layer-roles` 的总审计记录,old_value 摘要 / new_value 摘要(被改实体计数即可,详细审计走每实体的现有 audit hook)。每个被升/重排/降级/重挂的实体仍写一条对应 action 的 audit (沿用 `convert_to_chapter` 风格)。
9. **返回**:`{ chapter_map, new_lock_version }`。
   - `chapter_map` 用于前端把"被升叶子的旧 step_id"映射到"新 chapter_id";前端 reload 后理论上不需要(因为 reload 重新拉全树),但保留作为可观察契约 + 调试方便。

### 3.3 walk 等价性保证

- 抽出共享 fixture 文件 `frontend/tests/fixtures/layer-walk-fixtures.json` + `backend/tests/fixtures/layer_walk_fixtures.json`(symlink 或 build-time copy)。
- 至少 8 个 fixture:截图场景、L2+L3 嵌套、被夹紧的 L3、单行无收养、空文档、只有 chapter→content、混合多类型、深度溢出。
- 前后端单测分别加载并断言 walk 输出 `dict[id, LayerUpdate]` 完全相等。

### 3.4 事务边界 + 错误处理

- 整个 service 函数包裹在单个 SQLAlchemy 事务里 (router 层 `db.commit()` 在 service return 后调用)。任一阶段抛错 → 路由层 except → `db.rollback()` → 返回相应 400 / 409。
- `numbering_service.recompute` 必须在所有结构变更后调用一次(不要 per-phase 重算)。
- `optimistic_lock.bump` 在最后调用一次。

---

## §4 前端实现详解

### 4.1 `applyLayerRoles` action (`procedureEditor.ts:867`)

```ts
async applyLayerRoles(
  roleMap: Map<string, LayerRole>,
): Promise<{ ok: true } | { ok: false; conflicts: LayerConflict[] }> {
  const rows = this.layerRows
  const updates = computeLayerUpdates(rows, roleMap)
  const conflicts = validateLayerQ25(rows, updates)  // 已对齐 walk 末态
  if (conflicts.length > 0) return { ok: false, conflicts }

  const idMap = await this.ensureSaved()
  this.pushUndo('layer')

  const resolvedRoles: Record<string, LayerRole> = {}
  for (const [id, role] of roleMap) {
    resolvedRoles[idMap[id] ?? id] = role
  }

  try {
    await applyLayerRolesApi(this.procedure.id, {
      roles: resolvedRoles,
      lock_version: this.procedure.lock_version,
    })
  } catch (e) {
    if (isQ25ConflictError(e)) {
      return { ok: false, conflicts: e.body.conflicts }
    }
    throw e  // 409 / 5xx 由调用方 ChapterTreePanel 现有 try/catch 兜底
  }

  await this.reload()
  this.layerMode = false
  return { ok: true }
}
```

调用点(`ChapterTreePanel.vue` 的「应用层级」按钮)签名不变,继续使用 `{ok, conflicts}` 返回值。banner 渲染逻辑不动。

### 4.2 `validateLayerQ25` 改动 (`layerMark.ts:144`)

删掉对 `row.originalParent` 的引用,switch 改为统一用 `u.parent_id`:

```ts
switch (u.kind) {
  case 'reorder':       endOf.set(id, { kind: 'chapter', parent: u.parent_id }); break
  case 'to-content':    endOf.set(id, { kind: 'leaf',    parent: u.parent_id }); break
  case 'to-chapter':    endOf.set(id, { kind: 'chapter', parent: u.parent_id }); break
  case 'leaf-reparent': endOf.set(id, { kind: 'leaf',    parent: u.parent_id }); break
}
```

同步:
- `LayerRow` 类型移除 `originalParent` 字段。
- 文件顶部 `validateLayerQ25` JSDoc 改写,删除"前后端发散"段落,改为"前后端 walk 共享语义,按 walk 末态分组"。

### 4.3 视觉预览不变

`computeLayerIndents` 维持原状,继续按 walk 末态算缩进——这正是用户已经看到的"3.1 下方自动缩进"效果,本次只是让数据真的跟上。

---

## §5 测试

### 5.1 后端 (`backend/tests/unit/services/test_layer_apply_service.py`)

最少覆盖:
1. **单行升 L2 无后续叶子** → 新章节空 body 或仅一个 synthesized content。
2. **单行升 L2 + 2 后续叶子** → 收养 2 个为新章节子。
3. **截图场景(三行升 L2)** → 各自吃自己的收养块。
4. **L2 + 后续 L3** → L3 作为 L2 子章节,各自吃自己的收养块。
5. **L3 无 L2 上下文** → 夹到 L1。
6. **混入未被升的叶子,且不属于任一收养块** → 末态父下同时有章节+叶子 → 400 `SIBLING_TYPE_CONFLICT`,DB 未变。
7. **深度超 3** → 400 `CHAPTER_DEPTH_EXCEEDED`,事务回滚。
8. **章节 reorder + 叶子升级混合 batch** → 全部正确。
9. **乐观锁冲突** → 409 `OPTIMISTIC_LOCK`。
10. **空 roles map(noop)** → 200,无变化。
11. **roles map 中含 `keep` 显式标注** → 等价于不传。
12. **`to-content` on a chapter with chapter-children** → 400 `CHAPTER_HAS_CHILDREN`,事务回滚。
13. **batch 内 L2 + 紧随的 L3 叶子,L3 的 `u.parent_id` 指向 L2 的旧 leaf_id** → 通过 leaf_id→new_chapter_id map 解析,新 L3 章节的 parent_id 是新 L2 章节。
14. **`to-content` 章节为空标题** → 创建的 content step `content=""`(不是 `<p></p>`)。
15. **fixture 等价性测试**:加载共享 fixture,断言 backend walk 输出 = fixture 期望。

### 5.2 前端 (`frontend/tests/unit/`)

`utils/layerMark.test.ts`:
- 重写 `validateLayerQ25` 全部 case,验证新分组语义(末态而非 originalParent)。
- 新增 fixture-driven case 与后端 fixture 对齐。

`store/procedureEditor.test.ts`:
- mock `applyLayerRolesApi`,验证:
  - idMap 解析(temp id → real id);
  - 错误回传(Q25 → `{ok:false}`;其他 → throw);
  - reload 在成功路径被调用一次;
  - `layerMode` 在成功后清除。

### 5.3 端到端(可选,如已有 e2e harness)

- 截图场景:3.1/3.2/3.3 升 L2 + 应用 → DOM 树结构断言。
- 应用失败回滚:模拟 Q25 → DB 未变。

---

## §6 风险与缓解

| 风险 | 缓解 |
|---|---|
| 双端 walk 漂移 | 共享 fixture + 双端单测断言;e2e 截图场景兜底 |
| `pushUndo('layer')` 浅快照对新事务的可逆性 | 实施时先评估 reload 后 store 完整重建是否覆盖 undo 需求;不行则降级为 toast "层级应用不可撤销",不做完整 undo 重做 |
| 后端 walk 实现 bug 导致数据不一致 | 单事务回滚 + 充分的 fixture-driven 测试;首次上线前在 dev 数据上手动验证截图场景 |
| 性能(大文档,~500 行)| `numbering_service.recompute` 已是全量重算,无新瓶颈;若实测慢再优化 |
| `chapter_map` 契约的未来扩展 | 留作可观察字段,不强制前端消费;后续可加 `created_chapters` / `deleted_steps` 等 |

## §7 验收标准

1. 截图场景 (3.1/3.2/3.3 升 L2) 在 UI 上点应用后:
   - 无 §Q25 报错;
   - 树正确呈现三个 L2 章节,各带 2 个 content 子节点;
   - 编号 3.1/3.2/3.3 与原 Word 一致(若标题保留)。
2. 前后端单测全部通过;fixture 等价性测试通过。
3. 任一阶段失败 → DB 完全无变更(通过手工 SQL 验证 + 单测断言)。
4. `validateLayerQ25` 不再产生"应该让用户能升但被错误拦住"的假阳性。
5. `MEMORY.md` 中 `layer-overlay-q25-dryrun-gap` 标记为 SUPERSEDED 或删除。

## §8 实施顺序建议(供 writing-plans 参考)

1. 后端 fixture + walk 实现 (TDD)
2. 后端 service + router + schema
3. 后端单测 (含 fixture 等价性)
4. 前端 `validateLayerQ25` 改动 + 单测
5. 前端 API client + store action 重写
6. 前端 store 单测
7. 手动 dev 验证(截图场景 + 边界)
8. Memory 更新 + commit
