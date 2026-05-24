import { describe, it, expect } from 'vitest'
import {
  COL_DEFAULTS,
  COL_MIN,
  rightOf,
  resizeLeftMid,
  resizeMidRight,
  sanitizeCols,
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
})
