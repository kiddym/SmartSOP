import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { relativeTime } from '@/utils/format'

describe('relativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-05T12:00:00Z'))
  })
  afterEach(() => vi.useRealTimers())

  it('30 秒内 → 刚刚', () => {
    expect(relativeTime('2026-06-05T11:59:40Z')).toBe('刚刚')
  })
  it('分钟级', () => {
    expect(relativeTime('2026-06-05T11:55:00Z')).toBe('5 分钟前')
  })
  it('小时级', () => {
    expect(relativeTime('2026-06-05T09:00:00Z')).toBe('3 小时前')
  })
  it('天级', () => {
    expect(relativeTime('2026-06-03T12:00:00Z')).toBe('2 天前')
  })
  it('空值 → 空串', () => {
    expect(relativeTime(null)).toBe('')
  })
})
