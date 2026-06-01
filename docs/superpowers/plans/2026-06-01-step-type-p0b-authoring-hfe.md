# P0b — 编写侧人因增强：NCW 同页 + 步骤类型推断 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 两个相互独立、均不依赖执行态、在编写/PDF 阶段即有人因收益的增强：(A) **NCW 与其保护的步骤强制同页**（书 §4.2.5 + 原则九，防"翻页诱发的条件断裂"）；(B) **标记为步骤时按正文文本自动推断 step_type**（减少作者逐个手选）。

**Architecture:**
- (A) 纯后端 PDF：NCW 仍由 `input_schema.type ∈ {NOTE,CAUTION,WARNING}` 判定（NCW 归位是 P4）。在 `sections.py` 的步骤渲染循环加一个分组 pass：把"连续 NCW + 紧随其后的被保护步骤"用现有 `KeepTogether` 包成一组。
- (B) 纯前端：`utils/editor.ts` 加纯函数 `inferStepType(text)`；`store.setKind(id,'step')` 时若 `step_type` 为空则同批写入推断值。显示链路（P0 的 `effectiveStepType` / 色条 / 下拉）原样复用。

**前置依赖：** P0（`step_type` 列 + `effectiveStepType` + 下拉/色条）已合并。Spec：`docs/superpowers/specs/2026-06-01-step-type-mobile-execution-design.md`（P0b 行）。

**Tech Stack:** ReportLab + pytest（后端）；Vue 3 + Pinia + vitest（前端）。无新依赖。

---

## File Structure

- **Modify** `backend/app/services/pdf/sections.py` — 加 `_is_ncw` + `_render_steps` 分组 pass，`build_content` / `_render_chapter` 改用之。
- **Modify** `backend/tests/unit/services/pdf/test_sections.py` — NCW+步骤分组测试。
- **Modify** `frontend/src/utils/editor.ts` — `inferStepType`。
- **Modify** `frontend/tests/unit/editorUtils.spec.ts` — 推断测试。
- **Modify** `frontend/src/store/nodeEditor.ts` — `setKind` 转步骤时预填推断 step_type。

---

## Task 1: NCW 与被保护步骤强制同页（PDF）

**Files:** `backend/app/services/pdf/sections.py`, `backend/tests/unit/services/pdf/test_sections.py`

**约定（书 §4.2.5）：** 核电程序里 NCW 位于其保护步骤之前（先警告、后动作）。故把"一段连续 NCW + 紧随的首个非 NCW 步骤"绑为同页组。`content` 块（`kind=='content'`）不参与绑定（它无 type）。

- [ ] **Step 1: 先写失败测试** — append `backend/tests/unit/services/pdf/test_sections.py`（沿用该文件现有 RenderData/StepData 构造夹具；如无则参考 `test_context.py` 造最小 `RenderData`）：
```python
from reportlab.platypus import KeepTogether
from app.services.pdf import sections

def _step(id, ftype, kind="step", content="x"):
    from app.services.pdf.context import StepData
    return StepData(id=id, code="1", title="t", content=content, kind=kind,
                    skip_numbering=False, input_schema={"type": ftype}, attachment_marks=[])

def test_ncw_kept_with_following_step(make_render_data):
    data = make_render_data(root_steps=[_step("w", "WARNING"), _step("a", "COMMON")])
    out, _ = sections.build_content(data)
    # 警告 + 其后步骤被包进同一个 KeepTogether
    assert any(isinstance(f, KeepTogether) for f in out)

def test_lone_step_not_wrapped(make_render_data):
    data = make_render_data(root_steps=[_step("a", "COMMON")])
    out, _ = sections.build_content(data)
    assert not any(isinstance(f, KeepTogether) for f in out)
```
（若 `make_render_data` 夹具不存在，本步先在该测试文件内写一个最小工厂：构造 `RenderData`，仅填 `root_chapters=[]`、`root_steps=...`、`assets`/`procedure` 用最小桩。）
Run `cd backend && pytest tests/unit/services/pdf/test_sections.py -k ncw` → FAIL。

- [ ] **Step 2: 实现分组 pass** — [sections.py](../../../backend/app/services/pdf/sections.py) 加：
```python
def _is_ncw(st: StepData) -> bool:
    return st.kind == "step" and str((st.input_schema or {}).get("type", "")).upper() in (
        "NOTE", "CAUTION", "WARNING",
    )


def _render_steps(steps: list[StepData], data: RenderData, out: list[Flowable]) -> None:
    """逐步渲染；把"连续 NCW + 紧随的首个非 NCW 步骤"绑为 KeepTogether（§4.2.5 同页）。"""
    i, n = 0, len(steps)
    while i < n:
        if _is_ncw(steps[i]):
            j = i
            while j < n and _is_ncw(steps[j]):
                j += 1
            grp: list[Flowable] = []
            for k in range(i, j):
                _render_step(steps[k], data, grp)
            if j < n:  # 绑定被保护步骤
                _render_step(steps[j], data, grp)
                j += 1
            out.append(KeepTogether(grp))
            i = j
        else:
            _render_step(steps[i], data, out)
            i += 1
```
导入 `KeepTogether`：在 `from reportlab.platypus import ...` 行加入（若未导入）。

- [ ] **Step 3: 两处循环改用** — `build_content`（line 240 `for st in data.root_steps`）改为 `_render_steps(data.root_steps, data, out)`；`_render_chapter`（line 269 `for st in ch.steps`）改为 `_render_steps(ch.steps, data, out)`。

- [ ] **Step 4: 跑后端 PDF 测试** — `cd backend && pytest tests/unit/services/pdf tests/integration/test_pdf.py` → 全绿（含既有渲染回归）。

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/pdf/sections.py backend/tests/unit/services/pdf/test_sections.py
git commit -m "feat(pdf): keep NCW on same page as its protected step (P0b Task 1)"
```

---

## Task 2: 标记为步骤时按文本推断 step_type（前端）

**Files:** `frontend/src/utils/editor.ts`, `frontend/tests/unit/editorUtils.spec.ts`, `frontend/src/store/nodeEditor.ts`

- [ ] **Step 1: 先写失败测试** — append `editorUtils.spec.ts`：
```ts
import { inferStepType } from '@/utils/editor'

describe('inferStepType (从正文文本推断, 保守默认 action)', () => {
  it('如果/若/是否 → decision', () => {
    expect(inferStepType('如果压力低于 450kPa，则关闭阀门')).toBe('decision')
    expect(inferStepType('确认是否达到联锁条件')).toBe('decision')
  })
  it('等待/保持 N 分钟 → wait', () => {
    expect(inferStepType('等待 30 分钟至系统稳定')).toBe('wait')
  })
  it('批准/会签/暂停 → hold', () => {
    expect(inferStepType('暂停，待值长批准后继续')).toBe('hold')
  })
  it('记录/填写/读数 → data', () => {
    expect(inferStepType('记录 RCS 压力读数')).toBe('data')
  })
  it('转至/参见程序 → link', () => {
    expect(inferStepType('转至程序 OP-RCS-002 第 5 步')).toBe('link')
  })
  it('无信号 → action', () => {
    expect(inferStepType('启动补水泵')).toBe('action')
  })
})
```
Run `cd frontend && npm test -- tests/unit/editorUtils.spec.ts` → FAIL。

- [ ] **Step 2: 实现** — append [utils/editor.ts](../../../frontend/src/utils/editor.ts)：
```ts
// 有序关键词规则（命中即返回；顺序即优先级）。保守：无信号归 action（对齐原则三 NA 判定）。
const _INFER_RULES: ReadonlyArray<[StepType, RegExp]> = [
  ['decision', /如果|若|是否|当.*则|IF\b/i],
  ['wait',     /等待|保持|静置|稳定后|分钟后|秒后|min后/i],
  ['hold',     /批准|会签|暂停|持单|监督确认|HOLD/i],
  ['link',     /转至|跳转|参见程序|见程序|执行程序|见附录/i],
  ['data',     /记录|填写|读数|读取|测量|录入|抄录/i],
]
/** 从步骤正文纯文本推断 step_type；不臆造分支/门控时返回 action。 */
export function inferStepType(text: string): StepType {
  const t = (text ?? '').trim()
  for (const [type, re] of _INFER_RULES) if (re.test(t)) return type
  return 'action'
}
```
Run 同上 → PASS。

- [ ] **Step 3: 转步骤时预填** — [nodeEditor.ts](../../../frontend/src/store/nodeEditor.ts) 改 `setKind`（line 166）：转为 step 且当前 `step_type` 为空时，同批写入推断值。
```ts
    async setKind(id: string, kind: 'node' | 'step'): Promise<void> {
      if (!this.procedureId) return
      const cur = this.nodeMap.get(id)
      const prev = cur?.kind ?? 'node'
      const item: { kind: 'node' | 'step'; step_type?: import('@/types/node').StepType } = { kind }
      if (kind === 'step' && !cur?.step_type) {
        const plain = (cur?.body ?? '').replace(/<[^>]+>/g, ' ')
        item.step_type = inferStepType(plain)
      }
      this.nodes = await api.batchUpdateNodes(this.procedureId, { [id]: item })
      this._pushUndo(() => this.setKind(id, prev))
    },
```
顶部加 `import { inferStepType } from '@/utils/editor'`。
（推断仅在 step_type 为空时执行：不覆盖作者已选；撤销仍回退 kind，step_type 由作者后续显式调整——P0b 不为推断单独做撤销栈，保持简单。）

- [ ] **Step 4: 前端门禁** — `cd frontend && npm run typecheck`；`npm test`；`npm run build`。

- [ ] **Step 5: Commit**
```bash
git add frontend/src/utils/editor.ts frontend/tests/unit/editorUtils.spec.ts frontend/src/store/nodeEditor.ts
git commit -m "feat(editor): infer step_type from body text on mark-as-step (P0b Task 2)"
```

---

## Orchestrator browser smoke (after Task 2, before merge)

1. 把一个含"等待 30 分钟"的正文块标记为步骤 → 详情面板「步骤类型」自动显示「等待」，树行蓝色「等待」chip。
2. 把"记录读数"块设为步骤 → 自动「记录」（紫）。
3. 把"启动泵"块设为步骤 → 「执行」（灰，默认）。
4. 已手选过类型的步骤再切 kind 不被覆盖。
5. PDF 预览：一份在页尾放「警告」紧接动作步骤的程序 → 警告不会被单独留在页尾，与其后的动作步骤一起换到下一页（可用窄内容逼近页尾验证）。
6. 既有 PDF（封面/目录/修订/普通步骤）渲染无回归。

---

## Self-Review

**Spec 覆盖（P0b 行）：** NCW 同页强制可见（PDF KeepTogether 分组，先 NCW 后步骤）→ Task 1 ✓；step_type 文本推断（保守默认 action，转步骤时预填）→ Task 2 ✓。
**非目标：** NCW 归位为独立 notice 节点（P4）、执行态强制阅读确认「我已阅读」（P2）、解析器侧推断（解析器不产 step）——均不在 P0b。
**类型一致性：** `_is_ncw(StepData)->bool`、`_render_steps(list,RenderData,list)->None` 与现有 `_render_step` 同签名风格；`inferStepType(string)->StepType` 复用 P0 的 `StepType`。
**风险：** ① 连续多个被保护步骤共享一个 NCW 的场景较罕见，本实现只绑首个后继步骤——符合"一警一动作"的常见写法，多步绑定留待按需扩展；② `KeepTogether` 内容若超过一页高度，ReportLab 会自行降级拆页（不会无限留白），可接受。
