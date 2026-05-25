import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ http: { get } }))

import { fetchSourceDocx } from '@/api/procedures'

describe('fetchSourceDocx', () => {
  beforeEach(() => {
    get.mockReset()
  })

  it('解析 RFC5987 文件名并回传 blob（blob + skipErrorToast）', async () => {
    const blob = new Blob([new Uint8Array([1, 2, 3])])
    get.mockResolvedValue({
      data: blob,
      // quote('原文.docx') = %E5%8E%9F%E6%96%87.docx
      headers: { 'content-disposition': "attachment; filename*=UTF-8''%E5%8E%9F%E6%96%87.docx" },
    })
    const out = await fetchSourceDocx('p1')
    expect(out?.filename).toBe('原文.docx')
    expect(out?.blob).toBe(blob)
    expect(get.mock.calls[0][0]).toBe('/procedures/p1/source-docx')
    const cfg = get.mock.calls[0][1]
    expect(cfg.responseType).toBe('blob')
    expect(cfg.skipErrorToast).toBe(true)
  })

  it('无 content-disposition → 回退 source.docx', async () => {
    get.mockResolvedValue({ data: new Blob([]), headers: {} })
    const out = await fetchSourceDocx('p1')
    expect(out?.filename).toBe('source.docx')
  })

  it('请求失败 → null（不抛、不弹错）', async () => {
    get.mockRejectedValue(new Error('404'))
    expect(await fetchSourceDocx('p1')).toBeNull()
  })
})
