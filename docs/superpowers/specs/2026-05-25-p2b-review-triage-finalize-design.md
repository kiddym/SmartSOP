# P2b · 待确认 triage + 完成（发布拦截）设计

**日期：** 2026-05-25
**状态：** 已批准
**作者：** 协作设计（cui_yuming + Claude）
**上位文档：** `2026-05-25-unified-create-edit-model-overview-design.md`（北极星）；P2 拆为 P2a/P2b/P2c，本文是 **P2b**。

---

## 1. 背景与范围

P2a 已让导入把 `mark_status='review'` 带进草稿，并在编辑器只读暴露（行徽标 + 头部计数）。P2b 加上**处理**它们的交互，并让"完成（发布）"在仍有待确认时被拦。

**范围：**
1. 逐个「接受待确认」（清 review）。
2. 「全部接受」批量清 review。
3. 「只看待确认」过滤 + 「下一个待确认」逐个跳转。
4. 手动改 review 节点的类型/层级时自动清 review。
5. 「完成」=发布：仍有 review 则拦（后端校验 + 前端清单项）。

**非目标（→ P2c/P3）：** 5 选项层级标定批量视图；置信度/降型藏存；入口统一与下线。

## 2. 关键现状（探查确认）

- `mark_status='review'` 持久于 chapter；`store.chapters` 可读；P2a 已加行徽标 + `reviewCount` 计数。
- 清 review 已具备：后端 `POST /chapters/{id}/mark-status`（`mark_service.set_mark_status` 不校验取值，可 `review→unmarked`，不记审计、不 bump revision）；前端 `chaptersApi.setMarkStatus(id, status)` 与 `store.setMark(id, status)` 已能用（`setMark` 乐观更新 + 失败回滚；临时 id 只改本地）。
- 编辑器已有大量改型/改级 store 动作：`toggleContentType`（章节↔正文，本地可撤销）、`promoteChapter`/`demoteChapter`（后端即时、改后 reload）、`convertToStep`/`contentToSteps`/`convertToChapter`（跨实体、后端即时、节点会换 id）。
- 发布：`EditorTopBar` 发布按钮 → `PublishChecklistDialog` → `onPublishConfirm` → `transitionProcedure(PUBLISHED)`。后端 `procedure_service.transition` 已校验"版本更新说明(v>1)"与"必填自定义字段"；**无 review 校验**。

## 3. 决定

### D1 · 逐个「接受待确认」
- 选中节点 `mark_status==='review'` 时，节点详情面板（`ChapterDetailPanel` 与 `ContentDetailPanel`）显示「接受待确认」按钮。
- 动作：新增 store action `acceptReview(id)` = `setMark(id, 'unmarked')`（复用既有持久化）。
- 接受后徽标/计数随 `mark_status` 实时消失。

### D2 · 「全部接受」批量清
- 树面板头部 `reviewCount` 旁加「全部接受」按钮（仅 `reviewCount>0` 显示）。
- 动作：新增 store action `acceptAllReviews()`：先 `ensureSaved()`（保险），再对所有 `mark_status==='review'` 的 chapter 逐个 `setMark(id,'unmarked')`。
- 前端点按前 `ElMessageBox.confirm`（"将接受 N 个待确认节点，确认其解析结构无误？"）。

### D3 · 「只看待确认」过滤 + 「下一个待确认」
- 树面板加一个「只看待确认」开关（`reviewFilter` 本地态）：开启时 `visibleRows` 仅保留 `mark_status==='review'` 的行 + 其祖先（复用现有搜索的祖先保留逻辑）。与搜索互不冲突（同时生效取交集即可，简单起见：过滤开启时在现有 visibleRows 基础上再筛 review+祖先）。
- 「下一个待确认」按钮：在 review 节点间循环选中（按 `flatRows` 文档序找当前选中之后的下一个 review，选中它；无选中则选第一个），并滚动到可见。
- `reviewCount===0` 时这两个控件隐藏/禁用。

### D4 · 手动改类型/层级自动清 review
- 在 review 节点上做"解析判定的纠正"时，自动把它的 `mark_status` 从 `'review'` 清成 `'unmarked'`（视为已处理）：
  - 本地动作 `toggleContentType`：若该节点 `mark_status==='review'`，同时置 `'unmarked'`（本地，随保存持久化）。
  - 后端即时动作 `promoteChapter`/`demoteChapter`：成功后若原节点是 review，`setMark(id,'unmarked')`（同 id，reload 前后一致）。
  - 跨实体 `convertToStep`/`contentToSteps`/`convertToChapter`：节点被替换/重建，原 review 自然消失，无需特殊处理。
- 仅"纠正结构"的动作清 review；单纯改标题/正文内容**不**清（那不解决"结构是否正确"的疑问）。

### D5 · 「完成」=发布，仍有 review 则拦
- **后端** `procedure_service.transition`：`target=='PUBLISHED'` 时，若该程序存在 `mark_status=='review'` 的 active chapter，抛 `bad_request("REVIEW_PENDING", "仍有 N 个待确认节点，请先全部处理")`（放在现有版本说明/自定义字段校验旁）。
- **前端** `PublishChecklistDialog`：增加一项"无待确认节点"——`reviewCount>0` 时该项为未通过/红，确认发布按钮禁用或拦截，引导用户去处理。

## 4. 数据流

1. 进编辑器 → 看到待确认徽标/计数（P2a）。
2. 处理：逐个「接受」(D1) / 「全部接受」(D2) / 用「只看待确认」+「下一个」逐条核（D3）/ 直接改结构（D4 自动清）。
3. `reviewCount` 归零 → 发布清单"无待确认"通过 → 可「完成（发布）」。
4. 若没清完就点发布 → 后端 `REVIEW_PENDING` 拦（D5），前端清单已提前提示。

## 5. 边界与错误

- **review 全在临时节点上**：导入来的节点都是真实 id，`setMark` 直发后端；保险起见 `acceptAllReviews` 先 `ensureSaved`。
- **接受过程中失败**：`setMark` 单个失败自回滚该节点；批量遇错不静默——逐个进行，失败项保留 review（拦截器提示）。
- **过滤态下接受到空**：`reviewCount→0` 时自动关「只看待确认」或显示空态，不卡死。
- **并发/乐观锁**：`set_mark_status` 不 bump revision；发布走乐观锁不受影响。

## 6. 测试

- 后端：`transition→PUBLISHED` 在有 review 时返 `REVIEW_PENDING`（4xx）；清掉后可发布。（pytest）
- 前端：
  - `acceptReview` / `acceptAllReviews` store 动作（mock api，断言 mark_status 变化）。
  - `reviewFilter` 过滤 + `下一个待确认` 选中逻辑（纯/组件）。
  - D4：`toggleContentType`/`promoteChapter`/`demoteChapter` 在 review 节点上后 `mark_status==='unmarked'`。
  - 详情面板「接受待确认」按钮：review 节点显示、点按 emit/调 store。
  - `PublishChecklistDialog`：`reviewCount>0` 时拦发布。
  - Gate：前端 `lint+typecheck+test+build`；后端 `ruff+mypy+pytest`。

## 7. 文件清单（预估）

- 后端：`app/services/procedure_service.py`（transition 加 review 校验）；`tests/integration/test_procedures.py`（发布拦截测试）。
- 前端：
  - `store/procedureEditor.ts`：加 `acceptReview`、`acceptAllReviews`；`toggleContentType`/`promoteChapter`/`demoteChapter` 内自动清 review。
  - `components/editor/ChapterDetailPanel.vue` + `ContentDetailPanel.vue`：「接受待确认」按钮。
  - `components/editor/ChapterTreePanel.vue`：「全部接受」+「只看待确认」过滤 +「下一个待确认」+ 过滤逻辑。
  - `components/editor/PublishChecklistDialog.vue`：无待确认清单项 + 拦截。
  - 相应单测。

## 8. 留给 P2c/P3

- 5 选项层级标定批量视图（含置信度/降型藏存、章节↔步骤跨实体）。
- 入口统一与下线 beta2 / 老导入。
