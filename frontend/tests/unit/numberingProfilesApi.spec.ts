import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, put, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, put, delete: del } }))

import {
  createNumberingProfile,
  deleteNumberingProfile,
  listNumberingProfiles,
  updateNumberingProfile,
} from '@/api/numberingProfiles'

describe('numberingProfiles api', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: [] })
    post.mockReset().mockResolvedValue({ data: {} })
    put.mockReset().mockResolvedValue({ data: {} })
    del.mockReset().mockResolvedValue({ data: undefined })
  })

  it('listNumberingProfiles GET /numbering-profiles', async () => {
    await listNumberingProfiles()
    expect(get).toHaveBeenCalledWith('/numbering-profiles')
  })

  it('createNumberingProfile POST 带 pattern_key/kind/level', async () => {
    await createNumberingProfile('第X条', 'heading', 3)
    expect(post).toHaveBeenCalledWith('/numbering-profiles', {
      pattern_key: '第X条',
      kind: 'heading',
      level: 3,
    })
  })

  it('updateNumberingProfile PUT /numbering-profiles/{id}', async () => {
    await updateNumberingProfile('np1', { kind: 'list' })
    expect(put).toHaveBeenCalledWith('/numbering-profiles/np1', { kind: 'list' })
  })

  it('deleteNumberingProfile DELETE /numbering-profiles/{id}', async () => {
    await deleteNumberingProfile('np1')
    expect(del).toHaveBeenCalledWith('/numbering-profiles/np1')
  })
})
