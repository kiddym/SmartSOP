import { describe, it, expect } from 'vitest'
import { nextReviewId } from '@/utils/reviewNav'

const rows = [
  { id: 'a', mark_status: 'unmarked' as const },
  { id: 'b', mark_status: 'review' as const },
  { id: 'c', mark_status: 'review' as const },
  { id: 'd', mark_status: 'unmarked' as const },
]

describe('nextReviewId', () => {
  it('无选中 → 第一个 review', () => {
    expect(nextReviewId(rows, null)).toBe('b')
  })
  it('从某 review → 下一个 review', () => {
    expect(nextReviewId(rows, 'b')).toBe('c')
  })
  it('最后一个 review → 循环回第一个', () => {
    expect(nextReviewId(rows, 'c')).toBe('b')
  })
  it('当前在非 review 行 → 文档序之后的第一个 review（环绕）', () => {
    expect(nextReviewId(rows, 'd')).toBe('b')
  })
  it('无 review → null', () => {
    expect(nextReviewId([{ id: 'a', mark_status: 'unmarked' as const }], 'a')).toBeNull()
  })
})
