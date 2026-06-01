import { ElMessage } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as api from '@/api/batchImports'
import { useBatchReviewStore } from '@/store/batchReview'

const job = {
  id: 'j1', folder_id: 'f1', parse_mode: 'smart', status: 'reviewing',
  counts: { total: 2, parsed: 2, review: 2, applied: 0, failed: 0 }, created_at: '',
}
const items = [
  { id: 'i1', job_id: 'j1', filename: 'a.docx', status: 'review', content_hash: 'h1',
    summary: { chapter_count: 3, confidence_tier: 'high', warning_count: 0 }, review_revision: 1, error: null },
  { id: 'i2', job_id: 'j1', filename: 'b.docx', status: 'review', content_hash: 'h2',
    summary: { chapter_count: 5, confidence_tier: 'low', warning_count: 2 }, review_revision: 1, error: null },
]

const blob = { chapters: [], metadata: {}, assets: [], warnings: [],
  detected_patterns: [], validation: null, review_required: 0, parse_method: 'smart' }

describe('batchReview store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('loads job + items and computes risk-sorted rows', async () => {
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue(job as never)
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue(items as never)
    const store = useBatchReviewStore()
    await store.load('j1')
    expect(store.job?.id).toBe('j1')
    expect(store.items).toHaveLength(2)
    expect(store.riskSortedItems[0].id).toBe('i2')
    expect(store.highConfidenceIds).toEqual(['i1'])
  })

  it('applyReviewOps bumps local revision and reloads blob', async () => {
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue(job as never)
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue(items as never)
    vi.spyOn(api, 'fetchParseResult').mockResolvedValue(blob as never)
    const patchSpy = vi.spyOn(api, 'patchReviewItem').mockResolvedValue({ review_revision: 2 })

    const store = useBatchReviewStore()
    await store.load('j1')
    await store.openItem('i1')
    store.reviewRevision = 1
    await store.applyReviewOps([{ node_id: 'n1', action: 'to_content' }])
    expect(patchSpy).toHaveBeenCalledWith('j1', 'i1', { review_revision: 1, ops: [{ node_id: 'n1', action: 'to_content' }] })
    expect(store.reviewRevision).toBe(2)
  })

  it('openItem reads the item review_revision (not hardcoded 1)', async () => {
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue(job as never)
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue(
      [{ ...items[0], review_revision: 4 }] as never,
    )
    vi.spyOn(api, 'fetchParseResult').mockResolvedValue(blob as never)
    const store = useBatchReviewStore()
    await store.load('j1')
    await store.openItem('i1')
    expect(store.reviewRevision).toBe(4)
  })

  it('applyReviewOps swallows 409 (reload-wins): reloads authoritative revision, no throw', async () => {
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue(job as never)
    // 服务端权威版本已推进到 7（模拟他端连改两次）
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue(
      [{ ...items[0], review_revision: 7 }] as never,
    )
    const blobSpy = vi.spyOn(api, 'fetchParseResult').mockResolvedValue(blob as never)
    vi.spyOn(api, 'patchReviewItem').mockRejectedValue({ response: { status: 409 } })
    const warnSpy = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as never)

    const store = useBatchReviewStore()
    await store.load('j1')
    await store.openItem('i1') // fetchParseResult #1
    store.reviewRevision = 1 // 本地陈旧
    await expect(
      store.applyReviewOps([{ node_id: 'n1', action: 'accept' }]),
    ).resolves.toBeUndefined() // 不抛
    expect(warnSpy).toHaveBeenCalled()
    expect(store.reviewRevision).toBe(7) // 读权威版本（非盲猜 +1=2）
    expect(blobSpy).toHaveBeenCalledTimes(2) // openItem + reload-wins
  })

  it('applyReviewOps rethrows non-409 errors', async () => {
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue(job as never)
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue(items as never)
    vi.spyOn(api, 'fetchParseResult').mockResolvedValue(blob as never)
    vi.spyOn(api, 'patchReviewItem').mockRejectedValue({ response: { status: 500 } })

    const store = useBatchReviewStore()
    await store.load('j1')
    await store.openItem('i1')
    await expect(
      store.applyReviewOps([{ node_id: 'n1', action: 'accept' }]),
    ).rejects.toBeTruthy()
  })
})
