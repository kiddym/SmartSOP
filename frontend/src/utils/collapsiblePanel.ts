/** 折叠后竖条宽度，像素。 */
export const RAIL_PX = 32

/** 可折叠面板的折叠态与宽度（像素）。 */
export interface PanelState {
  collapsed: boolean
  width: number
}

/** 面板宽度配置：默认宽 + 边界。 */
export interface PanelConfig {
  defaultWidth: number
  min: number
  max: number
}

/** 夹到 [min, max]；非有限值回 defaultWidth。 */
export function clampWidth(w: number, cfg: PanelConfig): number {
  if (!Number.isFinite(w)) return cfg.defaultWidth
  return Math.min(Math.max(w, cfg.min), cfg.max)
}

/** 按像素增量调宽（夹紧），保持 collapsed。 */
export function resizePanel(start: PanelState, deltaPx: number, cfg: PanelConfig): PanelState {
  return { collapsed: start.collapsed, width: clampWidth(start.width + deltaPx, cfg) }
}

/** 拖拽有符号增量：left 列 splitter 在右缘（随右拖增大），right 列在左缘（随左拖增大）。 */
export function dragDelta(side: 'left' | 'right', clientX: number, startX: number): number {
  return side === 'left' ? clientX - startX : startX - clientX
}

/** 校验持久化值：非对象/脏值回 {collapsed:false, width:defaultWidth}；宽度夹紧；collapsed 仅认 boolean。 */
export function sanitizePanel(v: unknown, cfg: PanelConfig): PanelState {
  if (typeof v !== 'object' || v === null) return { collapsed: false, width: cfg.defaultWidth }
  const o = v as Record<string, unknown>
  if (typeof o.collapsed !== 'boolean' || typeof o.width !== 'number') {
    return { collapsed: false, width: cfg.defaultWidth }
  }
  return { collapsed: o.collapsed, width: clampWidth(o.width, cfg) }
}
