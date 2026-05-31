import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, put, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}))

vi.mock('@/api/http', () => ({ http: { get, post, put, delete: del } }))

import {
  createHeadingRule,
  deleteHeadingRule,
  listHeadingRules,
  updateHeadingRule,
} from '@/api/headingRules'

describe('headingRules api', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: [] })
    post.mockReset().mockResolvedValue({ data: {} })
    put.mockReset().mockResolvedValue({ data: {} })
    del.mockReset().mockResolvedValue({ data: undefined })
  })

  it('listHeadingRules GET /heading-rules', async () => {
    await listHeadingRules()
    expect(get).toHaveBeenCalledWith('/heading-rules')
  })

  it('createHeadingRule POST 带 style_name + level', async () => {
    await createHeadingRule('章节标题', 2)
    expect(post).toHaveBeenCalledWith('/heading-rules', { style_name: '章节标题', level: 2 })
  })

  it('updateHeadingRule PUT /heading-rules/{id}', async () => {
    await updateHeadingRule('r1', { status: 'candidate' })
    expect(put).toHaveBeenCalledWith('/heading-rules/r1', { status: 'candidate' })
  })

  it('deleteHeadingRule DELETE /heading-rules/{id}', async () => {
    await deleteHeadingRule('r1')
    expect(del).toHaveBeenCalledWith('/heading-rules/r1')
  })
})
