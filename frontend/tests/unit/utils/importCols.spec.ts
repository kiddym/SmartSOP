import { describe, it, expect } from 'vitest'
import {
  COL_DEFAULTS,
  COL_MIN,
  rightOf,
  resizeLeftMid,
  resizeMidRight,
  sanitizeCols,
  RAIL_PX,
  colFlex,
  sanitizeCollapsed,
} from '@/utils/importCols'

describe('importCols', () => {
  it('rightOf derives the remaining width', () => {
    expect(rightOf({ left: 38, mid: 28 })).toBe(34)
  })

  describe('resizeLeftMid (drag the left|mid handle)', () => {
    it('grows left and shrinks mid by the same delta; right unchanged', () => {
      const r = resizeLeftMid({ left: 38, mid: 28 }, 10)
      expect(r).toEqual({ left: 48, mid: 18 })
      expect(rightOf(r)).toBe(34)
    })

    it('shrinks left and grows mid on negative delta', () => {
      expect(resizeLeftMid({ left: 38, mid: 28 }, -10)).toEqual({ left: 28, mid: 38 })
    })

    it('clamps left to COL_MIN, never starving mid below COL_MIN', () => {
      const r = resizeLeftMid({ left: 38, mid: 28 }, -100)
      expect(r.left).toBe(COL_MIN)
      expect(r.mid).toBe(38 + 28 - COL_MIN)
    })

    it('clamps mid to COL_MIN when left grows too much', () => {
      const r = resizeLeftMid({ left: 38, mid: 28 }, 100)
      expect(r.mid).toBe(COL_MIN)
      expect(r.left).toBe(38 + 28 - COL_MIN)
    })

    it('returns finite widths when delta is NaN', () => {
      const r = resizeLeftMid({ left: 38, mid: 28 }, NaN)
      expect(Number.isFinite(r.left)).toBe(true)
      expect(Number.isFinite(r.mid)).toBe(true)
    })
  })

  describe('resizeMidRight (drag the mid|right handle)', () => {
    it('grows mid and shrinks right; left unchanged', () => {
      const r = resizeMidRight({ left: 38, mid: 28 }, 10)
      expect(r).toEqual({ left: 38, mid: 38 })
      expect(rightOf(r)).toBe(24)
    })

    it('clamps mid to COL_MIN on large negative delta', () => {
      const r = resizeMidRight({ left: 38, mid: 28 }, -100)
      expect(r).toEqual({ left: 38, mid: COL_MIN })
    })

    it('clamps right to COL_MIN when mid grows too much', () => {
      const r = resizeMidRight({ left: 38, mid: 28 }, 100)
      expect(rightOf(r)).toBe(COL_MIN)
      expect(r.mid).toBe(44)
    })
  })

  describe('sanitizeCols (guards persisted/dirty values)', () => {
    it('passes through a valid value', () => {
      expect(sanitizeCols({ left: 40, mid: 25 })).toEqual({ left: 40, mid: 25 })
    })

    it('falls back to defaults when a column is below COL_MIN', () => {
      expect(sanitizeCols({ left: 10, mid: 28 })).toEqual(COL_DEFAULTS)
    })

    it('falls back when left+mid leaves right below COL_MIN', () => {
      expect(sanitizeCols({ left: 60, mid: 30 })).toEqual(COL_DEFAULTS)
    })

    it('falls back on malformed input', () => {
      expect(sanitizeCols(null)).toEqual(COL_DEFAULTS)
      expect(sanitizeCols({ left: 'x' })).toEqual(COL_DEFAULTS)
    })
  })

  describe('colFlex (列 flex + 分隔条可见性)', () => {
    const cols = { left: 38, mid: 28 } // rightOf = 34

    it('都不折叠：三列按百分比权重，两个分隔条都显示', () => {
      const cf = colFlex(cols, { left: false, right: false })
      expect(cf).toEqual({
        left: '38 1 0%', mid: '28 1 0%', right: '34 1 0%',
        showLM: true, showMR: true,
      })
    })

    it('仅左折叠：左列变细条、左分隔条隐藏，中右保持权重', () => {
      const cf = colFlex(cols, { left: true, right: false })
      expect(cf.left).toBe(`0 0 ${RAIL_PX}px`)
      expect(cf.mid).toBe('28 1 0%')
      expect(cf.right).toBe('34 1 0%')
      expect(cf.showLM).toBe(false)
      expect(cf.showMR).toBe(true)
    })

    it('仅右折叠：右列变细条、右分隔条隐藏，左中保持权重', () => {
      const cf = colFlex(cols, { left: false, right: true })
      expect(cf.left).toBe('38 1 0%')
      expect(cf.mid).toBe('28 1 0%')
      expect(cf.right).toBe(`0 0 ${RAIL_PX}px`)
      expect(cf.showLM).toBe(true)
      expect(cf.showMR).toBe(false)
    })

    it('两侧都折叠：左右细条、两分隔条都隐藏，中列仍是唯一增长列', () => {
      const cf = colFlex(cols, { left: true, right: true })
      expect(cf.left).toBe(`0 0 ${RAIL_PX}px`)
      expect(cf.mid).toBe('28 1 0%')
      expect(cf.right).toBe(`0 0 ${RAIL_PX}px`)
      expect(cf.showLM).toBe(false)
      expect(cf.showMR).toBe(false)
    })
  })

  describe('sanitizeCollapsed (守卫持久化折叠状态)', () => {
    it('透传合法布尔对象', () => {
      expect(sanitizeCollapsed({ left: true, right: false })).toEqual({ left: true, right: false })
    })

    it('非对象 / null 回退全展开', () => {
      expect(sanitizeCollapsed(null)).toEqual({ left: false, right: false })
      expect(sanitizeCollapsed('x')).toEqual({ left: false, right: false })
    })

    it('字段非布尔或缺失：该字段按 false 处理', () => {
      expect(sanitizeCollapsed({ left: 'yes', right: 1 })).toEqual({ left: false, right: false })
      expect(sanitizeCollapsed({ left: true })).toEqual({ left: true, right: false })
    })
  })
})
