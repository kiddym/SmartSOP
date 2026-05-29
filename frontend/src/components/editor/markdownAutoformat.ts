// Markdown autoformat-on-type for the node-body wangeditor (E6).
// Pure decision functions (unit-tested) + a Slate plugin (browser-verified, added in Task 2).

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
