export interface DiffSeg {
  type: 'equal' | 'del' | 'ins'
  text: string
}

/** Visible text of a body HTML (for diffing). textContent concatenates — block breaks collapse. */
export function htmlToText(html: string): string {
  if (!html) return ''
  return new DOMParser().parseFromString(html, 'text/html').body.textContent ?? ''
}

const GUARD = 1_000_000

/** Char-level diff: common prefix/suffix trim, then char-LCS on the differing middle.
 *  Size guard: a huge fully-different middle degrades to one del + one ins (no O(n·m) blowup). */
export function charDiff(a: string, b: string): DiffSeg[] {
  if (a === b) return a ? [{ type: 'equal', text: a }] : []
  const minLen = Math.min(a.length, b.length)
  let p = 0
  while (p < minLen && a[p] === b[p]) p++
  let s = 0
  while (s < a.length - p && s < b.length - p && a[a.length - 1 - s] === b[b.length - 1 - s]) s++
  const aMid = a.slice(p, a.length - s)
  const bMid = b.slice(p, b.length - s)
  const segs: DiffSeg[] = []
  if (p > 0) segs.push({ type: 'equal', text: a.slice(0, p) })
  if (aMid && bMid && aMid.length * bMid.length > GUARD) {
    segs.push({ type: 'del', text: aMid })
    segs.push({ type: 'ins', text: bMid })
  } else {
    segs.push(...lcsMiddle(aMid, bMid))
  }
  if (s > 0) segs.push({ type: 'equal', text: a.slice(a.length - s) })
  return merge(segs)
}

function lcsMiddle(a: string, b: string): DiffSeg[] {
  if (!a) return b ? [{ type: 'ins', text: b }] : []
  if (!b) return [{ type: 'del', text: a }]
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const out: DiffSeg[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ type: 'equal', text: a[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: 'del', text: a[i] })
      i++
    } else {
      out.push({ type: 'ins', text: b[j] })
      j++
    }
  }
  while (i < n) {
    out.push({ type: 'del', text: a[i] })
    i++
  }
  while (j < m) {
    out.push({ type: 'ins', text: b[j] })
    j++
  }
  return out
}

/** Coalesce adjacent same-type segments; drop empties. */
function merge(segs: DiffSeg[]): DiffSeg[] {
  const out: DiffSeg[] = []
  for (const seg of segs) {
    if (!seg.text) continue
    const last = out[out.length - 1]
    if (last && last.type === seg.type) last.text += seg.text
    else out.push({ ...seg })
  }
  return out
}
