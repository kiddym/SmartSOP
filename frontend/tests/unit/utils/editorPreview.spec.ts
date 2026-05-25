import { describe, it, expect } from 'vitest'
import {
  PREVIEW_DEFAULTS,
  PREVIEW_MIN,
  PREVIEW_MAX,
  clampPreviewWidth,
  resizePreview,
  sanitizePreview,
} from '@/utils/editorPreview'

describe('editorPreview', () => {
  it('clampPreviewWidth 夹到 [MIN, MAX]，NaN 回默认', () => {
    expect(clampPreviewWidth(100)).toBe(PREVIEW_MIN)
    expect(clampPreviewWidth(9999)).toBe(PREVIEW_MAX)
    expect(clampPreviewWidth(500)).toBe(500)
    expect(clampPreviewWidth(Number.NaN)).toBe(PREVIEW_DEFAULTS.width)
  })

  it('resizePreview 按 deltaPx 调宽并夹紧；collapsed 透传', () => {
    expect(resizePreview({ collapsed: false, width: 400 }, 60)).toEqual({ collapsed: false, width: 460 })
    expect(resizePreview({ collapsed: false, width: 400 }, -1000).width).toBe(PREVIEW_MIN)
    expect(resizePreview({ collapsed: true, width: 400 }, 60).collapsed).toBe(true)
  })

  it('sanitizePreview：合法透传；脏值回默认；宽度夹紧', () => {
    expect(sanitizePreview({ collapsed: true, width: 500 })).toEqual({ collapsed: true, width: 500 })
    expect(sanitizePreview(null)).toEqual({ ...PREVIEW_DEFAULTS })
    expect(sanitizePreview({ collapsed: 'x', width: 'y' })).toEqual({ ...PREVIEW_DEFAULTS })
    expect(sanitizePreview({ collapsed: false, width: 99999 }).width).toBe(PREVIEW_MAX)
  })
})
