// Markdown autoformat-on-type for the node-body wangeditor (E6).
// Pure decision functions (unit-tested) + a Slate plugin (browser-verified, added in Task 2).

import {
  SlateEditor,
  SlateElement,
  SlateNode,
  SlateRange,
  SlateText,
  SlateTransforms,
  type IDomEditor,
} from '@wangeditor/editor'

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
      const closeStart = n - 2
      const open = text.lastIndexOf('**', closeStart - 1)
      if (open === -1) return null
      const innerStart = open + 2
      const innerEnd = closeStart
      if (innerEnd <= innerStart) return null
      if (text[innerStart] === '*' || text[innerEnd - 1] === '*') return null
      return { mark: 'bold', openStart: open, innerStart, innerEnd, closeEnd: n }
    }
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
  SlateTransforms.delete(editor, {
    at: { anchor: blockStart, focus: { path: blockStart.path, offset: rule.deleteLen } },
  })
  if (rule.type === 'blockquote') {
    SlateTransforms.setNodes(editor, { type: 'blockquote' } as unknown as Partial<SlateElement>, { at: path })
  } else {
    SlateTransforms.setNodes(
      editor,
      { type: 'list-item', ordered: rule.type === 'numbered', level: 0 } as unknown as Partial<SlateElement>,
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
    { [hit.mark]: true } as unknown as Partial<SlateText>,
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
