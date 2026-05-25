/** 编辑器 Word 预览列的折叠态与宽度（像素）。 */
export interface PreviewState {
  collapsed: boolean
  width: number
}

/** 默认：展开、460px。 */
export const PREVIEW_DEFAULTS: Readonly<PreviewState> = { collapsed: false, width: 460 }
/** 预览列宽度边界（像素）。 */
export const PREVIEW_MIN = 240
export const PREVIEW_MAX = 900

/** 夹到 [MIN, MAX]；非有限值回默认宽度。 */
export function clampPreviewWidth(w: number): number {
  if (!Number.isFinite(w)) return PREVIEW_DEFAULTS.width
  return Math.min(Math.max(w, PREVIEW_MIN), PREVIEW_MAX)
}

/** 按像素增量调宽（夹紧），保持 collapsed。 */
export function resizePreview(start: PreviewState, deltaPx: number): PreviewState {
  return { collapsed: start.collapsed, width: clampPreviewWidth(start.width + deltaPx) }
}

/** 校验持久化值：非对象/脏值回默认；宽度夹紧；collapsed 仅认 boolean。 */
export function sanitizePreview(v: unknown): PreviewState {
  if (typeof v !== 'object' || v === null) return { ...PREVIEW_DEFAULTS }
  const o = v as Record<string, unknown>
  if (typeof o.collapsed !== 'boolean' || typeof o.width !== 'number') return { ...PREVIEW_DEFAULTS }
  return { collapsed: o.collapsed, width: clampPreviewWidth(o.width) }
}
