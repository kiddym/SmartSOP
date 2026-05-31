import { describe, it, expect, vi, beforeEach } from 'vitest'

const post = vi.hoisted(() => vi.fn())
vi.mock('@/api/http', () => ({ http: { post, get: vi.fn() } }))

import { importFromWord } from '@/api/parse'

beforeEach(() => {
  post.mockReset()
  post.mockImplementation((url: string) => {
    if (url === '/uploads') return Promise.resolve({ data: { upload_token: 'tok', filename: 'a.docx' } })
    if (url === '/parse') return Promise.resolve({ data: { chapters: [{ id: 'c', title: 'X' }] } })
    if (url === '/procedures/import') return Promise.resolve({ data: { id: 'p1', code: 'QC-1' } })
    return Promise.reject(new Error('unexpected ' + url))
  })
})

describe('importFromWord', () => {
  it('依次 upload→parse→import，返回新程序', async () => {
    const file = new File(['x'], 'a.docx')
    const proc = await importFromWord(file, 'f1', '我的程序', 'continuous')
    expect(proc.id).toBe('p1')
    const urls = post.mock.calls.map((c) => c[0])
    expect(urls).toEqual(['/uploads', '/parse', '/procedures/import'])
    const body = post.mock.calls[2][1]
    expect(body).toMatchObject({
      name: '我的程序',
      folder_id: 'f1',
      level_of_use: 'continuous',
      upload_token: 'tok',
    })
    expect(body.chapters).toHaveLength(1)
  })
})
