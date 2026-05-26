import { describe, it, expect } from 'vitest'
import { decideAutoCollapse } from '@/utils/sidebarAutoCollapse'

describe('decideAutoCollapse', () => {
  it('进入 library 路由 → collapse', () => {
    expect(decideAutoCollapse('/procedures/drafts', '/procedures/library', false)).toBe('collapse')
  })

  it('从其他根路由进入 library → collapse', () => {
    expect(decideAutoCollapse('/folders', '/procedures/library', false)).toBe('collapse')
  })

  it('离开 library 路由 → restore', () => {
    expect(decideAutoCollapse('/procedures/library', '/folders', false)).toBe('restore')
  })

  it('在 library 内部跳转 → noop', () => {
    expect(decideAutoCollapse('/procedures/library', '/procedures/library', false)).toBe('noop')
  })

  it('library 之外跳转 → noop', () => {
    expect(decideAutoCollapse('/folders', '/settings', false)).toBe('noop')
  })

  it('userOverride=true → 永远 noop（用户接管）', () => {
    expect(decideAutoCollapse('/procedures/drafts', '/procedures/library', true)).toBe('noop')
    expect(decideAutoCollapse('/procedures/library', '/folders', true)).toBe('noop')
  })
})
