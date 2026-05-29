# E6 — Markdown Autoformat-on-Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Typing markdown shortcuts in the node-body rich-text editor transforms them into rich formatting in place — additive, never losing existing content.

**Architecture:** A wangeditor v5 Slate plugin (`Boot.registerPlugin`) wraps `editor.insertText`. The *decision* logic is two pure, unit-tested functions; the *Slate application* is thin glue wrapped in try/catch so typing can never break. Spec: `docs/superpowers/specs/2026-05-29-editor-e6-markdown-autoformat-design.md`.

**Tech Stack:** Vue 3, @wangeditor/editor v5 (Slate-based), vitest, vue-tsc. No new runtime dependency.

**Confirmed wangeditor facts (from node_modules):** `@wangeditor/editor` exports `Boot` (static `registerPlugin(plugin)`) and re-exports `SlateTransforms, SlateEditor, SlateNode, SlateElement, SlateText, SlateRange, SlatePoint` from slate. List item node = `{ type: 'list-item', ordered: boolean, level: number, children }` (`ordered:false`→`<ul>`, `true`→`<ol>`). Blockquote = `{ type: 'blockquote' }`. Marks = `bold` / `italic` / `code`.

---

## File Structure

- **Create** `frontend/src/components/editor/markdownAutoformat.ts` — `detectBlockTrigger`, `detectInlineTrigger` (pure) + `withMarkdownAutoformat` (Slate glue).
- **Create** `frontend/tests/unit/editor/markdownAutoformat.spec.ts` — pure-function tests.
- **Modify** `frontend/src/components/editor/RichTextEditor.vue` — register the plugin once before editor creation.

No backend change. wangeditor cannot mount in jsdom, so the Slate glue's behavior is verified by an **orchestrator browser smoke** (below), not vitest.

---

## Task 1: Pure trigger-detection functions

**Files:**
- Create: `frontend/src/components/editor/markdownAutoformat.ts` (pure exports first)
- Test: `frontend/tests/unit/editor/markdownAutoformat.spec.ts`

- [ ] **Step 1: Write the failing test — CREATE `frontend/tests/unit/editor/markdownAutoformat.spec.ts`**

```ts
import { describe, it, expect } from 'vitest'
import { detectBlockTrigger, detectInlineTrigger } from '@/components/editor/markdownAutoformat'

describe('detectBlockTrigger', () => {
  it('bullet markers -, *, +', () => {
    expect(detectBlockTrigger('-')).toEqual({ type: 'bulleted', deleteLen: 1 })
    expect(detectBlockTrigger('*')).toEqual({ type: 'bulleted', deleteLen: 1 })
    expect(detectBlockTrigger('+')).toEqual({ type: 'bulleted', deleteLen: 1 })
  })
  it('numbered markers 1. and 12.', () => {
    expect(detectBlockTrigger('1.')).toEqual({ type: 'numbered', deleteLen: 2 })
    expect(detectBlockTrigger('12.')).toEqual({ type: 'numbered', deleteLen: 3 })
  })
  it('blockquote marker >', () => {
    expect(detectBlockTrigger('>')).toEqual({ type: 'blockquote', deleteLen: 1 })
  })
  it('null when not at block start or unsupported', () => {
    expect(detectBlockTrigger(' -')).toBeNull()   // leading space → not at start
    expect(detectBlockTrigger('x-')).toBeNull()   // text before marker
    expect(detectBlockTrigger('#')).toBeNull()    // headings deferred
    expect(detectBlockTrigger('1')).toBeNull()    // no dot
    expect(detectBlockTrigger('1)')).toBeNull()   // only "1." supported
    expect(detectBlockTrigger('')).toBeNull()
  })
})

describe('detectInlineTrigger', () => {
  it('bold **x**', () => {
    expect(detectInlineTrigger('**bold**')).toEqual({
      mark: 'bold', openStart: 0, innerStart: 2, innerEnd: 6, closeEnd: 8,
    })
  })
  it('italic *x* and _x_', () => {
    expect(detectInlineTrigger('*it*')).toEqual({ mark: 'italic', openStart: 0, innerStart: 1, innerEnd: 3, closeEnd: 4 })
    expect(detectInlineTrigger('_it_')).toEqual({ mark: 'italic', openStart: 0, innerStart: 1, innerEnd: 3, closeEnd: 4 })
  })
  it('code `x`', () => {
    expect(detectInlineTrigger('`c`')).toEqual({ mark: 'code', openStart: 0, innerStart: 1, innerEnd: 2, closeEnd: 3 })
  })
  it('does NOT fire mid-bold (single closing * inside **…*)', () => {
    expect(detectInlineTrigger('**bold*')).toBeNull()
  })
  it('null for incomplete / empty / non-delimiter end', () => {
    expect(detectInlineTrigger('**bold')).toBeNull() // no closing
    expect(detectInlineTrigger('``')).toBeNull()     // empty code
    expect(detectInlineTrigger('**')).toBeNull()     // empty bold
    expect(detectInlineTrigger('plain')).toBeNull()  // ends in non-delimiter
    expect(detectInlineTrigger('* x *')).toMatchObject({ mark: 'italic' }) // spaces allowed inside
  })
  it('respects leading text (offsets relative to string start)', () => {
    expect(detectInlineTrigger('say `hi`')).toEqual({ mark: 'code', openStart: 4, innerStart: 5, innerEnd: 7, closeEnd: 8 })
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/editor/markdownAutoformat.spec.ts`
Expected: FAIL — module/functions don't exist.

- [ ] **Step 3: Implement the pure functions — CREATE `frontend/src/components/editor/markdownAutoformat.ts`**

```ts
// Markdown autoformat-on-type for the node-body wangeditor (E6).
// Pure decision functions (unit-tested) + a Slate plugin (browser-verified).

export interface BlockTrigger {
  type: 'bulleted' | 'numbered' | 'blockquote'
  deleteLen: number
}

/** prefix = the block's text from its start to the caret, at the instant a space is typed
 *  (the space is NOT yet in the string). Returns a rule only for a recognized marker at block start. */
export function detectBlockTrigger(prefix: string): BlockTrigger | null {
  if (prefix === '-' || prefix === '*' || prefix === '+') return { type: 'bulleted', deleteLen: 1 }
  if (prefix === '>') return { type: 'blockquote', deleteLen: 1 }
  if (/^\d+\.$/.test(prefix)) return { type: 'numbered', deleteLen: prefix.length }
  return null
}

export interface InlineTrigger {
  mark: 'bold' | 'italic' | 'code'
  openStart: number
  innerStart: number
  innerEnd: number
  closeEnd: number
}

/** text = the caret's text-leaf content up to and including the just-typed closing delimiter.
 *  Returns the span to wrap, or null if no completed delimiter pair ends at the caret. */
export function detectInlineTrigger(text: string): InlineTrigger | null {
  if (!text) return null
  const n = text.length
  const last = text[n - 1]

  if (last === '`') {
    const open = text.lastIndexOf('`', n - 2)
    if (open === -1) return null
    const innerStart = open + 1
    const innerEnd = n - 1
    if (innerEnd <= innerStart) return null
    return { mark: 'code', openStart: open, innerStart, innerEnd, closeEnd: n }
  }

  if (last === '_') {
    const open = text.lastIndexOf('_', n - 2)
    if (open === -1) return null
    const innerStart = open + 1
    const innerEnd = n - 1
    if (innerEnd <= innerStart) return null
    return { mark: 'italic', openStart: open, innerStart, innerEnd, closeEnd: n }
  }

  if (last === '*') {
    if (text[n - 2] === '*') {
      // closing "**" → bold; need an opening "**" before it, non-empty inner not edged by '*'
      const closeStart = n - 2
      const open = text.lastIndexOf('**', closeStart - 1)
      if (open === -1) return null
      const innerStart = open + 2
      const innerEnd = closeStart
      if (innerEnd <= innerStart) return null
      if (text[innerStart] === '*' || text[innerEnd - 1] === '*') return null
      return { mark: 'bold', openStart: open, innerStart, innerEnd, closeEnd: n }
    }
    // single closing "*" → italic; need a lone "*" opener (neighbors not '*')
    const closeStart = n - 1
    let open = -1
    for (let i = closeStart - 1; i >= 0; i--) {
      if (text[i] === '*' && text[i - 1] !== '*' && text[i + 1] !== '*') {
        open = i
        break
      }
    }
    if (open === -1) return null
    const innerStart = open + 1
    const innerEnd = closeStart
    if (innerEnd <= innerStart) return null
    if (text[innerStart] === '*' || text[innerEnd - 1] === '*') return null
    return { mark: 'italic', openStart: open, innerStart, innerEnd, closeEnd: n }
  }

  return null
}
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/editor/markdownAutoformat.spec.ts`
Expected: PASS. If `'* x *'` or any case fails, fix the function (not the test) — the spec rules are authoritative.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/markdownAutoformat.ts frontend/tests/unit/editor/markdownAutoformat.spec.ts
git commit -m "feat(editor): pure markdown trigger detection (block + inline) (E6 Task 1)"
```

---

## Task 2: Slate plugin + register in RichTextEditor

**Files:**
- Modify: `frontend/src/components/editor/markdownAutoformat.ts` (append the glue)
- Modify: `frontend/src/components/editor/RichTextEditor.vue` (register once)

This task's behavior is verified by the orchestrator browser smoke (wangeditor can't mount in jsdom). The implementer's job is correct code + vue-tsc clean + the full vitest suite staying green.

- [ ] **Step 1: Append the Slate glue to `frontend/src/components/editor/markdownAutoformat.ts`**

```ts
import {
  SlateEditor,
  SlateElement,
  SlateNode,
  SlateRange,
  SlateText,
  SlateTransforms,
  type IDomEditor,
} from '@wangeditor/editor'

function applyBlock(editor: IDomEditor): boolean {
  const blockEntry = SlateEditor.above(editor, {
    match: (n) => SlateElement.isElement(n) && SlateEditor.isBlock(editor, n),
  })
  if (!blockEntry) return false
  const [block, path] = blockEntry
  // Only transform a plain paragraph (don't re-trigger inside list-item / blockquote / table cell).
  if (!SlateElement.isElement(block) || (block as { type?: string }).type !== 'paragraph') return false
  const sel = editor.selection
  if (!sel) return false
  const blockStart = SlateEditor.start(editor, path)
  const prefix = SlateEditor.string(editor, { anchor: blockStart, focus: sel.anchor })
  const rule = detectBlockTrigger(prefix)
  if (!rule) return false
  // Delete the marker chars at block start (they live in the first text leaf).
  SlateTransforms.delete(editor, {
    at: { anchor: blockStart, focus: { path: blockStart.path, offset: rule.deleteLen } },
  })
  if (rule.type === 'blockquote') {
    SlateTransforms.setNodes(editor, { type: 'blockquote' } as Partial<SlateElement>, { at: path })
  } else {
    SlateTransforms.setNodes(
      editor,
      { type: 'list-item', ordered: rule.type === 'numbered', level: 0 } as Partial<SlateElement>,
      { at: path },
    )
  }
  return true
}

function applyInline(editor: IDomEditor): void {
  const sel = editor.selection
  if (!sel) return
  const caret = sel.anchor
  const leaf = SlateNode.get(editor, caret.path)
  if (!SlateText.isText(leaf)) return
  const text = leaf.text.slice(0, caret.offset) // this leaf, up to the just-typed delimiter
  const hit = detectInlineTrigger(text)
  if (!hit) return
  const pt = (offset: number) => ({ path: caret.path, offset })
  // Delete closing then opening delimiter (closing first to keep earlier offsets valid).
  SlateTransforms.delete(editor, { at: { anchor: pt(hit.innerEnd), focus: pt(hit.closeEnd) } })
  SlateTransforms.delete(editor, { at: { anchor: pt(hit.openStart), focus: pt(hit.innerStart) } })
  const innerLen = hit.innerEnd - hit.innerStart
  SlateTransforms.setNodes(
    editor,
    { [hit.mark]: true } as Partial<SlateText>,
    { at: { anchor: pt(hit.openStart), focus: pt(hit.openStart + innerLen) }, match: SlateText.isText, split: true },
  )
  SlateTransforms.collapse(editor, { edge: 'end' })
  SlateEditor.removeMark(editor, hit.mark) // so the next typed char isn't marked
}

/** wangeditor v5 plugin: markdown autoformat-on-type. Registered once via Boot.registerPlugin. */
export function withMarkdownAutoformat<T extends IDomEditor>(editor: T): T {
  const { insertText } = editor
  editor.insertText = (text: string): void => {
    try {
      const sel = editor.selection
      if (sel && SlateRange.isCollapsed(sel)) {
        if (text === ' ') {
          if (applyBlock(editor)) return // marker consumed, space dropped
        } else if (text === '*' || text === '_' || text === '`') {
          insertText(text) // land the closing delimiter first
          try {
            applyInline(editor)
          } catch {
            /* leave the literal char; never double-insert */
          }
          return
        }
      }
    } catch {
      /* fall through to default insert */
    }
    insertText(text)
  }
  return editor
}
```

> If vue-tsc rejects a Slate node-shape cast, widen the cast (e.g. `as unknown as Partial<SlateElement>`) — do not loosen the pure functions or the editor types. Report the exact error if one blocks you.

- [ ] **Step 2: Register the plugin in `frontend/src/components/editor/RichTextEditor.vue`**

Add to the `<script setup>` imports (near line 4-6, after the existing wangeditor imports):
```ts
import { Boot } from '@wangeditor/editor'
import { withMarkdownAutoformat } from './markdownAutoformat'
```
Then, at module scope (top level of `<script setup>`, before the component logic — e.g. right after the imports), register once, HMR-safe:
```ts
// Register markdown autoformat once for all wangeditor instances (HMR-safe via a global flag).
const MD_PLUGIN_KEY = '__smartsop_md_autoformat_registered__'
if (!(globalThis as Record<string, unknown>)[MD_PLUGIN_KEY]) {
  Boot.registerPlugin(withMarkdownAutoformat)
  ;(globalThis as Record<string, unknown>)[MD_PLUGIN_KEY] = true
}
```
Change nothing else in the component (no template/props change).

- [ ] **Step 3: Type check**

Run: `cd frontend && npm run typecheck`
Expected: vue-tsc no errors.

- [ ] **Step 4: Full suite — green**

Run: `cd frontend && npm test`
Expected: 0 failures. Existing tests are unaffected (consumers stub `RichTextEditor`; `Boot.registerPlugin` only registers — it does not create an editor — so it won't throw in jsdom). The Task 1 pure-function tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/markdownAutoformat.ts frontend/src/components/editor/RichTextEditor.vue
git commit -m "feat(editor): wangeditor markdown autoformat plugin, registered in RichTextEditor (E6 Task 2)"
```

---

## Orchestrator browser smoke (NOT a subagent task — run after Task 2, before merge)

wangeditor needs a real DOM, so this is the feature's primary behavioral verification. Bootstrap the worktree backend (symlink `.venv`, cp `.env`, cp `dev.db`, symlink `var/storage`) + launch backend + frontend, open an existing procedure's editor (`/procedures/<id>/edit`), select a node, focus the body, and via chrome-devtools `evaluate_script` / `fill` type into the editor:

1. `- ` at the start of an empty paragraph → DOM shows `<ul><li>`.
2. `1. ` → `<ol><li>`.
3. `> ` → `<blockquote>`.
4. `**bold**` → `<strong>bold</strong>`; `*it*` → `<em>it</em>`; `` `c` `` → `<code>c</code>`.
5. A mid-paragraph `- ` (text before it) does NOT convert.
6. Ctrl+Z after an autoformat reverts to the literal markdown text.
7. Sanity: existing tables / a note-block in a body are untouched by unrelated typing.

If staging proves impractical, smoke against the parent `main` immediately after merge (the try/catch fallback guarantees typing never breaks regardless); note whichever was done.

---

## Self-Review

**Spec coverage:**
- Pure `detectBlockTrigger` / `detectInlineTrigger` → Task 1. ✓
- `withMarkdownAutoformat` wrapping `insertText`, block-on-space + inline-on-delimiter, try/catch fallback → Task 2 Step 1. ✓
- Registered once via `Boot.registerPlugin`, HMR-safe, before editor creation → Task 2 Step 2. ✓
- Feature set: `-`/`*`/`+`/`1.`/`>` + `**`/`*`/`_`/`` ` `` → covered by both functions + glue. ✓
- Additive / never lose content (only transforms the caret's leaf / current paragraph) → `applyBlock` requires `type === 'paragraph'`; `applyInline` works on the caret's text leaf. ✓
- Native undo (Slate ops) → no custom undo code. ✓
- Browser smoke as primary verification → orchestrator section. ✓
- Non-goals (headings, links, tables, source/paste mode) → no code touches them. ✓

**Placeholder scan:** none — full code for both functions and the glue; the only conditional is the cast-widening fallback with an explicit instruction.

**Type consistency:** `detectBlockTrigger`/`detectInlineTrigger` signatures + return shapes match between Task 1 definition, the tests, and `applyBlock`/`applyInline`. wangeditor exports used (`SlateEditor/SlateElement/SlateNode/SlateRange/SlateText/SlateTransforms/Boot/IDomEditor`) are all confirmed present.
