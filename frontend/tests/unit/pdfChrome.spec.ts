import { describe, it, expect } from 'vitest'
import { clampZoom, stepZoom, fitZoom, activePageIndex, clampPageInput, pageLabel, ZOOM_MIN, ZOOM_MAX } from '@/components/PdfPreview/pdfChrome'

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
  it('attributes the page even when the scroll lands short of its top (snap tolerance)', () => {
    // real-world: pages at [88,1229,2369,3510,4717], jumped to page idx 3 but scrollTop 65px short
    expect(activePageIndex(3446, [88, 1229, 2369, 3510, 4717])).toBe(3)
  })
})

describe('clampPageInput', () => {
  it('parses a 1-based page to a clamped 0-based index', () => {
    expect(clampPageInput('3', 12)).toBe(2)
    expect(clampPageInput(3, 12)).toBe(2)
  })
  it('clamps out-of-range to first/last', () => {
    expect(clampPageInput('0', 12)).toBe(0)
    expect(clampPageInput('99', 12)).toBe(11)
    expect(clampPageInput('-4', 12)).toBe(0)
  })
  it('null for non-numeric, empty, or no pages', () => {
    expect(clampPageInput('abc', 12)).toBeNull()
    expect(clampPageInput('', 12)).toBeNull()
    expect(clampPageInput('5', 0)).toBeNull()
  })
})

describe('pageLabel', () => {
  function page(html: string, cls = 'page'): HTMLElement {
    const el = document.createElement('section')
    el.className = cls
    el.innerHTML = html
    return el
  }
  it('cover page → 封面', () => {
    expect(pageLabel(page('<h1 class="cover-title">公司运营管理</h1>', 'page cover'), 0)).toBe('封面')
  })
  it('section page → its .sec-title text', () => {
    expect(pageLabel(page('<span class="ph-title">运营</span><h2 class="sec-title">目录</h2>'), 1)).toBe('目录')
  })
  it('content page → first .chapter-title text (ignores the running .ph-title)', () => {
    expect(pageLabel(page('<span class="ph-title">运营</span><h1 class="chapter-title">1.0 目的</h1>'), 3)).toBe('1.0 目的')
  })
  it('step page → first .step-title text', () => {
    expect(pageLabel(page('<div class="step-title">启动电源</div>'), 4)).toBe('启动电源')
  })
  it('no heading (only running header) → 第 N 页 fallback', () => {
    expect(pageLabel(page('<span class="ph-title">运营</span>'), 6)).toBe('第 7 页')
  })
})
