import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, del } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), del: vi.fn() }))

vi.mock('@/api/http', () => ({ http: { get, post, delete: del } }))

import {
  listAttachments,
  uploadAttachment,
  downloadAttachment,
  deleteAttachment,
} from '@/api/attachments'

// list/upload 挂在 /procedures/{id}/attachments；单附件 download/delete 后端扁平挂
// /attachments/{id}（见 backend/app/routers/attachments.py），不带 procedures 前缀。
describe('附件 api 路径对齐后端', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: new Blob(['x']) })
    post.mockReset().mockResolvedValue({ data: [] })
    del.mockReset().mockResolvedValue({ data: null, status: 204 })
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:stub')
    globalThis.URL.revokeObjectURL = vi.fn()
  })

  it('listAttachments 走 GET /procedures/{id}/attachments', async () => {
    await listAttachments('p1')
    expect(get).toHaveBeenCalledWith('/procedures/p1/attachments')
  })

  it('uploadAttachment 走 POST /procedures/{id}/attachments', async () => {
    await uploadAttachment('p1', [new File(['x'], 'a.pdf')])
    expect(post).toHaveBeenCalledWith('/procedures/p1/attachments', expect.any(FormData))
  })

  it('downloadAttachment 走 GET /attachments/{id}/download（无 procedures 前缀）', async () => {
    await downloadAttachment('a1')
    expect(get).toHaveBeenCalledWith('/attachments/a1/download', { responseType: 'blob' })
  })

  it('deleteAttachment 走 DELETE /attachments/{id}（无 procedures 前缀）', async () => {
    await deleteAttachment('a1')
    expect(del).toHaveBeenCalledWith('/attachments/a1')
  })
})
