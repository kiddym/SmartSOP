# E13 — PDF Preview Labeled Page Rail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A toggleable left outline rail in the PDF preview — one row per page (№ + first heading), active = current page, click → jump.

**Architecture:** Pure `pageLabel` in `pdfChrome.ts`; the dialog body restructures to a flex `[ .pv-rail | .pv-scroll ]`, reusing E7/E12 `goPage`/`currentPage`/`pageCount`/`pageEls`. Spec: `docs/superpowers/specs/2026-05-29-editor-e13-pdf-page-rail-design.md`.

**Tech Stack:** Vue 3, vitest + jsdom, vue-tsc. No new dependency.

---

## File Structure

- **Modify** `frontend/src/components/PdfPreview/pdfChrome.ts` — add `pageLabel`.
- **Modify** `frontend/tests/unit/pdfChrome.spec.ts` — `pageLabel` tests.
- **Modify** `frontend/src/components/PdfPreview/PdfPreviewDialog.vue` — rail state, items, toggle, body restructure, CSS.

No backend change. Rail rendering/restructure is browser-verified (jsdom has no layout); `pageLabel` is unit-tested.

---

## Task 1: Pure `pageLabel`

**Files:**
- Modify: `frontend/src/components/PdfPreview/pdfChrome.ts`
- Test: `frontend/tests/unit/pdfChrome.spec.ts`

- [ ] **Step 1: Write the failing tests — append to `frontend/tests/unit/pdfChrome.spec.ts`**

Add `pageLabel` to the existing `@/components/PdfPreview/pdfChrome` import line. Append:
```ts
describe('pageLabel', () => {
  function page(html: string, cls = 'page'): HTMLElement {
    const el = document.createElement('section')
    el.className = cls
    el.innerHTML = html
    return el
  }
  it('cover page → 封面', () => {
    expect(pageLabel(page('<h1 class="cover-title">公司运营管理</h1>', 'page cover'), 0)).toBe('封面')
  })
  it('section page → its .sec-title text', () => {
    expect(pageLabel(page('<span class="ph-title">运营</span><h2 class="sec-title">目录</h2>'), 1)).toBe('目录')
  })
  it('content page → first .chapter-title text (ignores the running .ph-title)', () => {
    expect(pageLabel(page('<span class="ph-title">运营</span><h1 class="chapter-title">1.0 目的</h1>'), 3)).toBe('1.0 目的')
  })
  it('step page → first .step-title text', () => {
    expect(pageLabel(page('<div class="step-title">启动电源</div>'), 4)).toBe('启动电源')
  })
  it('no heading (only running header) → 第 N 页 fallback', () => {
    expect(pageLabel(page('<span class="ph-title">运营</span>'), 6)).toBe('第 7 页')
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/pdfChrome.spec.ts` → FAIL (`pageLabel` not exported).

- [ ] **Step 3: Implement — append to `frontend/src/components/PdfPreview/pdfChrome.ts`**

```ts
/** Outline label for a preview .page element: 封面 for the cover; else the first section
 *  heading (.sec-title / .chapter-title / .step-title) text; fallback `第 N 页`.
 *  Ignores the running page-header (.ph-title, the repeated procedure name). */
export function pageLabel(el: HTMLElement, index: number): string {
  if (el.classList.contains('cover')) return '封面'
  const h = el.querySelector('.sec-title, .chapter-title, .step-title')
  const text = h?.textContent?.trim() ?? ''
  return text || `第 ${index + 1} 页`
}
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/pdfChrome.spec.ts` → expect all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PdfPreview/pdfChrome.ts frontend/tests/unit/pdfChrome.spec.ts
git commit -m "feat(pdf): pure pageLabel for the preview page rail (E13 Task 1)"
```

---

## Task 2: The rail in `PdfPreviewDialog.vue`

**Files:**
- Modify: `frontend/src/components/PdfPreview/PdfPreviewDialog.vue`

No new unit test (rail layout/scroll needs real layout; jsdom has none). Verified by vue-tsc + full suite + the orchestrator browser smoke; `pageLabel` is unit-tested in Task 1.

- [ ] **Step 1: Import `pageLabel`**

Add `pageLabel` to the existing `./pdfChrome` import (currently `import { stepZoom, fitZoom, activePageIndex, clampPageInput, ZOOM_MIN, ZOOM_MAX } from './pdfChrome'`):
```ts
import { stepZoom, fitZoom, activePageIndex, clampPageInput, pageLabel, ZOOM_MIN, ZOOM_MAX } from './pdfChrome'
```

- [ ] **Step 2: Add rail state**

Near the other refs (after `const currentPage = ref(0)`, ~line 42):
```ts
const railOpen = ref(true)
const railEl = ref<HTMLElement | null>(null)
const railItems = ref<{ index: number; label: string }[]>([])
```

- [ ] **Step 3: Build `railItems` on model load**

In the `watch(visible)` success branch, right after `pageCount.value = pageEls().length` (~line 108), add:
```ts
      railItems.value = pageEls().map((el, i) => ({ index: i, label: pageLabel(el, i) }))
```

- [ ] **Step 4: Keep the active rail row in view**

Add after the existing `watch(...)`/handlers (anywhere in `<script setup>`, e.g. after the `watch(visible …)` block):
```ts
watch(currentPage, () => {
  void nextTick(() => {
    railEl.value?.querySelector<HTMLElement>('.pv-rail-item.is-active')?.scrollIntoView({ block: 'nearest' })
  })
})
```

- [ ] **Step 5: Toolbar toggle**

In `.pv-actions` (line 169), add as the FIRST child (before `<div v-if="model" class="pv-zoom">`):
```html
          <el-button v-if="model && pageCount" size="small" :type="railOpen ? 'primary' : 'default'" @click="railOpen = !railOpen">☰ 目录</el-button>
```

- [ ] **Step 6: Body restructure — wrap `.pv-scroll` in `.pv-body` + add the rail**

The `.pv-scroll` block currently spans line 197 (`<div ref="scrollEl" … class="pv-scroll" @scroll="onScroll">`) through its matching `</div>` at line 352 (just before `</el-dialog>`). Wrap that whole block in a new `.pv-body` and add the rail aside as `.pv-body`'s first child:

Change line 197 from:
```html
    <div ref="scrollEl" v-loading="loading" class="pv-scroll" @scroll="onScroll">
```
to (insert the `.pv-body` open + the rail BEFORE the unchanged `.pv-scroll` line):
```html
    <div class="pv-body">
      <aside v-if="railOpen && model" ref="railEl" class="pv-rail no-print">
        <button
          v-for="it in railItems"
          :key="it.index"
          class="pv-rail-item"
          :class="{ 'is-active': it.index === currentPage }"
          @click="goPage(it.index)"
        >
          <span class="pv-rail-num">{{ it.index + 1 }}</span>
          <span class="pv-rail-label">{{ it.label }}</span>
        </button>
      </aside>
      <div ref="scrollEl" v-loading="loading" class="pv-scroll" @scroll="onScroll">
```
Then add one closing `</div>` after the `.pv-scroll` block's closing `</div>` (line 352) — i.e. between line 352 and `</el-dialog>` (line 353):
```html
        </div>
      </div>
    </div>
  </el-dialog>
```
(That is: `.pv-doc` close, `.pv-scroll` close, **new** `.pv-body` close, then `</el-dialog>`. Preserve the existing indentation of the inner content.)

- [ ] **Step 7: CSS** (in `<style scoped>`)

Change the `.pv-scroll` rule (line 390-…) — remove the fixed height (it moves to `.pv-body`) and make it flex-fill:
```css
.pv-body {
  display: flex;
  height: calc(100vh - 90px);
}
.pv-scroll {
  flex: 1;
  min-width: 0;
  overflow: auto;
  background: #525659;
  padding: 24px 0;
}
.pv-rail {
  width: 200px;
  flex: none;
  overflow-y: auto;
  background: #3a3d42;
  padding: 8px 0;
}
.pv-rail-item {
  display: flex;
  gap: 6px;
  width: 100%;
  text-align: left;
  padding: 4px 10px;
  background: none;
  border: none;
  color: #cfd3dc;
  cursor: pointer;
  font-size: 12px;
  line-height: 1.4;
}
.pv-rail-item:hover {
  background: rgba(255, 255, 255, 0.08);
}
.pv-rail-item.is-active {
  background: var(--el-color-primary, #d97757);
  color: #fff;
}
.pv-rail-num {
  flex: none;
  width: 20px;
  text-align: right;
  opacity: 0.7;
}
.pv-rail-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```
(Keep the original `.pv-scroll`'s `background`/`padding` values — only `height` moved to `.pv-body` and `flex:1; min-width:0` was added. The `@media print` block already hides `.no-print`, so the rail won't print; no print-CSS change needed.)

- [ ] **Step 8: Type check + full suite**

Run: `cd frontend && npm run typecheck` → vue-tsc no errors.
Run: `cd frontend && npm test` → 0 failures.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/PdfPreview/PdfPreviewDialog.vue
git commit -m "feat(pdf): toggleable labeled page rail in PdfPreviewDialog (E13 Task 2)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 2, before merge)

Launch the worktree dev servers; open a multi-page procedure (37-node `356e353c…`) → `PDF 预览`. Then:
1. The rail lists labeled rows (封面 / 目录 / 修订记录 / 1.0 目的 / …); the current page's row is highlighted.
2. Click a rail row → the canvas jumps to that page and the row highlights.
3. Scroll the canvas → the highlight follows and the active row scrolls into view in the rail.
4. `☰ 目录` toggles the rail off/on; with it off the preview is full-width.
5. E7/E12 still work (zoom +/−/适应, prev/next, jump-to-page input).
6. Print preview (or `@media print` emulation) shows no rail.

---

## Self-Review

**Spec coverage:**
- Pure `pageLabel` (cover/sec/chapter/step/fallback, ignores `.ph-title`) → Task 1. ✓
- Toggleable `.pv-rail` aside, row = № + label, `is-active`=`currentPage`, click→`goPage` → Task 2 Steps 5-6. ✓
- `railItems` built on model load; active-row-into-view watch → Task 2 Steps 3-4. ✓
- Body restructure to flex `[rail|scroll]`, `scrollEl` unchanged (E7/E12 intact); rail `.no-print` → Task 2 Steps 6-7. ✓
- Non-goals (scaled thumbnails, resizable, reorder, nested tree, persist) → untouched. ✓

**Placeholder scan:** none — full code for the helper, the template, and the CSS.

**Type consistency:** `pageLabel(el: HTMLElement, index: number): string` defined Task 1, imported + used Task 2 Step 3. `railItems: { index: number; label: string }[]`; the `v-for` binds `it.index`/`it.label`; `goPage(it.index)` matches E7's `goPage(i: number)`. `railOpen`/`railEl` typed. `currentPage`/`pageCount`/`pageEls`/`goPage`/`scrollEl` already exist (E7/E12).
