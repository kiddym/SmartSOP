import { describe, it, expect } from 'vitest'
import { shouldAutoCollapse } from '@/utils/editorFocus'

describe('editorFocus.shouldAutoCollapse', () => {
  it('来自导入且侧边栏展开 → true', () => {
    expect(shouldAutoCollapse('import', false)).toBe(true)
  })
  it('来自导入但侧边栏已折叠 → false', () => {
    expect(shouldAutoCollapse('import', true)).toBe(false)
  })
  it('非导入来源 → false', () => {
    expect(shouldAutoCollapse('other', false)).toBe(false)
    expect(shouldAutoCollapse(undefined, false)).toBe(false)
    expect(shouldAutoCollapse(['import'], false)).toBe(false)
  })
})
