import { describe, it, expect } from 'vitest'
import { clampZoom, stepZoom, fitZoom, activePageIndex, ZOOM_MIN, ZOOM_MAX } from '@/components/PdfPreview/pdfChrome'

describe('clampZoom', () => {
  it('clamps below min and above max', () => {
    expect(clampZoom(0.3)).toBe(ZOOM_MIN)
    expect(clampZoom(3)).toBe(ZOOM_MAX)
  })
  it('rounds to 2 decimals and passes valid values', () => {
    expect(clampZoom(1.234)).toBe(1.23)
    expect(clampZoom(0.7)).toBe(0.7)
  })
})

describe('stepZoom', () => {
  it('steps in/out by 0.1', () => {
    expect(stepZoom(1, 1)).toBe(1.1)
    expect(stepZoom(1, -1)).toBe(0.9)
  })
  it('clamps at the bounds', () => {
    expect(stepZoom(0.5, -1)).toBe(0.5)
    expect(stepZoom(2, 1)).toBe(2)
    expect(stepZoom(1.95, 1)).toBe(2)
  })
})

describe('fitZoom', () => {
  it('fits page width into the container minus padding', () => {
    expect(fitZoom(1048, 1000)).toBe(1)     // (1048-48)/1000
    expect(fitZoom(548, 1000)).toBe(0.5)    // (548-48)/1000
  })
  it('clamps and handles unmeasured page width', () => {
    expect(fitZoom(2048, 1000)).toBe(2)     // (2048-48)/1000 = 2.0
    expect(fitZoom(100, 1000)).toBe(0.5)    // tiny → clamp to min
    expect(fitZoom(1000, 0)).toBe(1)        // unmeasured → 1
  })
})

describe('activePageIndex', () => {
  it('returns 0 for empty', () => {
    expect(activePageIndex(123, [])).toBe(0)
  })
  it('tracks the last page whose top is <= scrollTop', () => {
    const tops = [0, 300, 600]
    expect(activePageIndex(0, tops)).toBe(0)
    expect(activePageIndex(350, tops)).toBe(1)
    expect(activePageIndex(300, tops)).toBe(1)   // exact boundary → that page
    expect(activePageIndex(10000, tops)).toBe(2) // past last → last
  })
})
