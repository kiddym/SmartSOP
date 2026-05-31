import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('@/api/http', () => ({ http: { get, post } }))

import {
  fetchParseMethods,
  importFromWord,
  importProcedure,
  parseDocx,
  uploadAsset,
  uploadDocx,
} from '@/api/parse'

describe('parse api', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: {} })
    post.mockReset().mockResolvedValue({ data: {} })
  })

  it('uploadDocx 以 multipart FormData 发到 /uploads', async () => {
    const file = new File([new Uint8Array([1, 2, 3])], 'a.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    await uploadDocx(file)
    expect(post).toHaveBeenCalledTimes(1)
    const [url, body, cfg] = post.mock.calls[0]
    expect(url).toBe('/uploads')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('file')).toBe(file)
    // multipart 头由调用方显式给出（覆盖 http 默认 json）
    expect(cfg.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('uploadDocx 透传上传进度回调', async () => {
    const file = new File([new Uint8Array([1])], 'b.docx')
    const onProgress = vi.fn()
    await uploadDocx(file, onProgress)
    const cfg = post.mock.calls[0][2]
    expect(typeof cfg.onUploadProgress).toBe('function')
  })

  it('fetchParseMethods 走 GET /parse/methods', async () => {
    get.mockResolvedValue({ data: [{ key: 'smart', label: '智能', description: 'd' }] })
    const out = await fetchParseMethods()
    expect(get).toHaveBeenCalledWith('/parse/methods')
    expect(out[0].key).toBe('smart')
  })

  it('parseDocx 提交 upload_token + parse_mode + 放宽超时', async () => {
    await parseDocx('tok-1', 'standard')
    expect(post).toHaveBeenCalledWith(
      '/parse',
      { upload_token: 'tok-1', parse_mode: 'standard' },
      { timeout: 45_000 },
    )
  })

  it('importProcedure POST /procedures/import 携带 chapters', async () => {
    const payload = {
      name: '记录控制程序',
      folder_id: 'f1',
      description: '',
      chapters: [
        {
          title: '目的',
          content_type: 'chapter' as const,
          rich_content: '',
          skip_numbering: false,
          mark_status: 'unmarked' as const,
          children: [],
        },
      ],
    }
    await importProcedure(payload)
    expect(post).toHaveBeenCalledWith('/procedures/import', payload)
  })

  it('importFromWord 串 upload→parse→import 并按序回报阶段', async () => {
    post.mockImplementation((url: string) => {
      if (url === '/uploads') return Promise.resolve({ data: { upload_token: 'tk' } })
      if (url === '/parse') return Promise.resolve({ data: { chapters: [{ title: 'x' }] } })
      return Promise.resolve({ data: { id: 'p1', code: 'QC-1' } }) // /procedures/import
    })
    const stages: string[] = []
    const out = await importFromWord(
      new File([new Uint8Array([1])], 'a.docx'),
      'f1',
      '名',
      'continuous',
      (s) => stages.push(s),
    )
    expect(out.id).toBe('p1')
    expect(stages).toEqual(['uploading', 'parsing', 'creating'])
    const importCall = post.mock.calls.find((c) => c[0] === '/procedures/import')
    expect(importCall?.[1]).toMatchObject({
      name: '名',
      folder_id: 'f1',
      level_of_use: 'continuous',
      upload_token: 'tk',
    })
  })

  it('uploadAsset 以 multipart 发到 /procedures/{id}/assets', async () => {
    const file = new File([new Uint8Array([9])], 'p.png', { type: 'image/png' })
    await uploadAsset('proc-9', file)
    const [url, body, cfg] = post.mock.calls[0]
    expect(url).toBe('/procedures/proc-9/assets')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('file')).toBe(file)
    expect(cfg.headers['Content-Type']).toBe('multipart/form-data')
  })
})
