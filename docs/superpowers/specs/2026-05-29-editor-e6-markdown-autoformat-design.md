# E6 — Markdown Autoformat-on-Type in the Node Body — Design

**Date:** 2026-05-29
**Track:** Post-migration node-editor enhancements (follows E1 undo/redo, E2 cascading multi-select, E3 Tab indent, E4 409 conflict recovery, E5 virtual list).
**Status:** Design approved; ready for implementation plan.

## Goal

Let authors type markdown shortcuts in the node-body rich-text editor and have them transform into rich formatting **in place, as they type** — additive, never losing existing content (tables, images, the custom note/caution/warning/signature/hold-point blocks).

## Background

- The node `body` is an HTML string edited in `frontend/src/components/editor/RichTextEditor.vue`, which wraps **@wangeditor/editor v5.1.x** (Slate-based). Hosted by `NodeDetailPanel.vue`, bound to `node.body`, debounced 500ms → `store.updateBody`.
- wangeditor v5 has **no built-in markdown**; no markdown library is installed.
- **Node structure (heading level) lives on the node** (`heading_level`, set via the tree chips / E3 Tab), **not** in the body. The body's first block element is the node title; the rest is content. So markdown `#` headings are *not* a useful body feature — the valuable shortcuts are inline emphasis, lists, and blockquote.
- The body also contains things markdown cannot represent — tables, images, and `<div class="note-block|caution-block|warning-block|signature-bar|hold-point">` blocks the PDF renderer keys on. The feature must be **additive** (transform only what the user just typed) so none of these can be lost.
- `RichTextEditor` is not unit-tested directly (consumers like `NodeDetailPanel.spec` stub it); wangeditor needs a real DOM and does not mount meaningfully in jsdom.

## Approach (chosen: autoformat-on-type via a wangeditor/Slate plugin)

Rejected alternatives (from brainstorming): **paste-as-markdown** (safe & simple but no live typing) and **source-mode toggle** (lossy HTML↔markdown round-trip drops tables / special blocks). Autoformat-on-type was chosen for the best authoring feel; its cost is the deepest integration.

**Isolation strategy:** split the *decision* (pure, unit-testable strings) from the *application* (thin Slate glue, browser-verified).

## Components

### New module — `frontend/src/components/editor/markdownAutoformat.ts`

**Pure decision functions (exported, unit-tested):**

```ts
export interface BlockTrigger { type: 'bulleted' | 'numbered' | 'blockquote'; deleteLen: number }
// prefix = the block's text from its start up to the caret, at the moment a space is typed.
// Returns a rule only when the prefix is exactly a recognized marker at block start.
export function detectBlockTrigger(prefix: string): BlockTrigger | null

export interface InlineTrigger {
  mark: 'bold' | 'italic' | 'code'
  openStart: number   // index of the first opening-delimiter char
  innerStart: number  // index of the first content char
  innerEnd: number    // index after the last content char
  closeEnd: number    // index after the last closing-delimiter char
}
// text = the current block's text up to and including the just-typed closing delimiter.
// Returns a span to wrap, or null if no completed delimiter pair ends at the caret.
export function detectInlineTrigger(text: string): InlineTrigger | null
```

Rules:
- **Block** (on space): prefix `-` / `*` / `+` → `bulleted`; `1.` (a digit run then `.`) → `numbered`; `>` → `blockquote`. Each `deleteLen` = marker length (the trailing space is consumed by the plugin, not inserted). Returns `null` if the prefix has anything before the marker (i.e. not at block start) or doesn't match.
- **Inline** (on typing a closing `*`, `_`, or `` ` ``): scan back from the caret for the matching opener. `**…**` → `bold`; single `*…*` or `_…_` → `italic`; `` `…` `` → `code`. Inner span must be non-empty and must not itself be only delimiters. `null` otherwise.

**Slate glue (exported):**

```ts
export function withMarkdownAutoformat<T extends IDomEditor>(editor: T): T
```

Wraps `editor.insertText`:
1. If `text === ' '`: read the block's leading text via wangeditor's re-exported Slate utils (`SlateEditor`, `SlateRange`, `SlateNode`, `SlatePoint`); if `detectBlockTrigger` returns a rule, delete the marker chars and convert the block (`SlateTransforms` — set the node to wangeditor's list-item shape, or wrap in a `blockquote` element), then **return without inserting the space**.
2. Else if `text` is one of `* _ \``: call the original `insertText(text)` (so the char lands), then read the block text up to the caret; if `detectInlineTrigger` returns a span, delete the closing+opening delimiter ranges and apply the mark to the inner range via `SlateTransforms.setNodes({ [mark]: true }, { match: text node, split: true })`.
3. Else: original `insertText(text)`.

The whole wrapped body is in **`try { … } catch { return original.insertText(text) }`** so a transform bug can never block typing.

> Implementation note (resolved in the plan): the exact wangeditor list-item node shape and the `SlateTransforms` calls for "paragraph → list item" must be confirmed against `@wangeditor/editor`'s exports during implementation; `blockquote` and the inline marks are straightforward.

### `RichTextEditor.vue`

- Import the module and register the plugin **once** before editor creation: `Boot.registerPlugin(withMarkdownAutoformat)`, guarded by a module-level `registered` flag so repeated imports/HMR don't double-register.
- No template/props change. Applies to both `variant: 'full'` and `'step'`. `readOnly` already prevents `insertText`, so no extra guard.

## Data flow

```
user types "- " ─▶ editor.insertText(' ')
   wrapper reads block prefix "-" ─▶ detectBlockTrigger("-") = {bulleted, deleteLen:1}
   ─▶ SlateTransforms: delete "-", convert block to list-item ─▶ (space consumed)
user types "**bold*" then "*" ─▶ insertText('*') (char lands) ─▶ block text "**bold**"
   ─▶ detectInlineTrigger("**bold**") = {bold, …} ─▶ strip "**" ×2, set bold on "bold"
```

Save/title/PDF are unaffected: the result is ordinary body HTML (`<ul><li>`, `<ol><li>`, `<blockquote>`, `<strong>`, `<em>`, `<code>`) flowing through the existing `onChange` → debounced `updateBody`.

## Undo

Transforms are Slate ops, so wangeditor's **native Ctrl+Z** reverts an autoformat (best-effort single step; no custom undo merging). Consistent with E1's "text-undo stays in the editor; the store undo stack is for structural ops" — the store stack is untouched.

## Error handling / risk

- **Highest-risk item in the series** — it touches wangeditor's Slate internals. The try/catch fallback guarantees typing never breaks.
- Because wangeditor needs a real DOM, the Slate glue **cannot be meaningfully unit-tested in jsdom**; the browser smoke is this feature's primary behavioral verification. The two pure functions carry the unit coverage.

## Testing

- **Unit — `frontend/tests/unit/editor/markdownAutoformat.spec.ts`** (pure functions only):
  - `detectBlockTrigger`: `-`/`*`/`+` → bulleted; `1.`/`12.` → numbered; `>` → blockquote; `null` for ` -` (leading space → not at start), `x-` (text before), `#` (deferred), empty.
  - `detectInlineTrigger`: `**b**` → bold; `*i*`/`_i_` → italic; `` `c` `` → code; `null` for `**b` (incomplete), `` `` `` (empty), `**` only, plain text ending in a non-delimiter.
- **Browser smoke (required, primary):** in a real editor, type each shortcut and assert the produced HTML (`<ul><li>`, `<ol><li>`, `<blockquote>`, `<strong>`, `<em>`, `<code>`); confirm a mid-paragraph `- ` does **not** transform; confirm Ctrl+Z reverts an autoformat to its literal text.
- Existing suite stays green (consumers stub `RichTextEditor`; no jsdom wangeditor test exists to break). `Boot.registerPlugin` at module load must not throw in jsdom (it only registers; it doesn't create an editor).
- vue-tsc clean.

## Non-goals (YAGNI)

- Source-mode toggle; paste-as-markdown.
- `#` headings (node structure is `heading_level`), `[text](url)` links, strikethrough, images, tables, task lists, and other GFM — all reachable via the existing toolbar.
- Custom undo merging (rely on native wangeditor undo).
- Markdown export / round-trip of existing HTML.
