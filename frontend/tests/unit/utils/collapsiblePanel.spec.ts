import { describe, it, expect } from 'vitest'
import {
  RAIL_PX,
  clampWidth,
  resizePanel,
  dragDelta,
  sanitizePanel,
  type PanelConfig,
} from '@/utils/collapsiblePanel'

const cfg: PanelConfig = { defaultWidth: 360, min: 300, max: 700 }

describe('collapsiblePanel', () => {
  it('RAIL_PX 为 32', () => {
    expect(RAIL_PX).toBe(32)
  })

  it('clampWidth 夹到 [min, max]，非有限回 defaultWidth', () => {
    expect(clampWidth(100, cfg)).toBe(300)
    expect(clampWidth(9999, cfg)).toBe(700)
    expect(clampWidth(500, cfg)).toBe(500)
    expect(clampWidth(Number.NaN, cfg)).toBe(360)
  })

  it('resizePanel 按 delta 调宽并夹紧；collapsed 透传', () => {
    expect(resizePanel({ collapsed: false, width: 400 }, 50, cfg)).toEqual({ collapsed: false, width: 450 })
    expect(resizePanel({ collapsed: false, width: 400 }, -1000, cfg).width).toBe(300)
    expect(resizePanel({ collapsed: true, width: 400 }, 50, cfg).collapsed).toBe(true)
  })

  it('dragDelta：left = x - x0，right = x0 - x', () => {
    expect(dragDelta('left', 120, 100)).toBe(20)
    expect(dragDelta('right', 120, 100)).toBe(-20)
    expect(dragDelta('right', 80, 100)).toBe(20)
  })

  it('sanitizePanel：合法透传；脏值回默认；宽度夹紧', () => {
    expect(sanitizePanel({ collapsed: true, width: 500 }, cfg)).toEqual({ collapsed: true, width: 500 })
    expect(sanitizePanel(null, cfg)).toEqual({ collapsed: false, width: 360 })
    expect(sanitizePanel({ collapsed: 'x', width: 'y' }, cfg)).toEqual({ collapsed: false, width: 360 })
    expect(sanitizePanel({ collapsed: false, width: 99999 }, cfg).width).toBe(700)
  })
})
