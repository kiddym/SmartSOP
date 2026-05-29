import { describe, it, expect } from 'vitest'
import { computeWindow, scrollOffsetFor, MIN_TO_VIRTUALIZE } from '@/composables/useVirtualRows'

describe('computeWindow', () => {
  it('renders all when the viewport is unmeasured (height 0)', () => {
    expect(computeWindow(0, 0, 500)).toEqual({ start: 0, end: 500, padTop: 0, padBottom: 0 })
  })
  it('renders all when total <= minToVirtualize', () => {
    expect(computeWindow(0, 300, MIN_TO_VIRTUALIZE)).toEqual({
      start: 0, end: MIN_TO_VIRTUALIZE, padTop: 0, padBottom: 0,
    })
  })
  it('windows the middle with overscan', () => {
    // scrollTop 600, viewport 300, total 100, rowH 30, overscan 8 → first 20, visible 10 → start 12, end 38
    expect(computeWindow(600, 300, 100)).toEqual({ start: 12, end: 38, padTop: 360, padBottom: 1860 })
  })
  it('clamps start at 0 near the top', () => {
    const w = computeWindow(0, 300, 100)
    expect(w.start).toBe(0)
    expect(w.padTop).toBe(0)
  })
  it('clamps end at total near the bottom', () => {
    const w = computeWindow(100 * 30, 300, 100)
    expect(w.end).toBe(100)
    expect(w.padBottom).toBe(0)
  })
})

describe('scrollOffsetFor', () => {
  it('returns null when the row is already visible', () => {
    expect(scrollOffsetFor(10, 0, 600)).toBeNull() // row 10 spans [300,330) within [0,600)
  })
  it('aligns to the top when the row is above the viewport', () => {
    expect(scrollOffsetFor(2, 300, 300)).toBe(60) // top 60 < scrollTop 300
  })
  it('aligns to the bottom when the row is below the viewport', () => {
    expect(scrollOffsetFor(30, 0, 300)).toBe(630) // bottom 930 - viewport 300
  })
  it('returns null when the viewport is unmeasured', () => {
    expect(scrollOffsetFor(5, 0, 0)).toBeNull()
  })
})
