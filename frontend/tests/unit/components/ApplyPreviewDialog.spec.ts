import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

import * as api from '@/api/batchImports'
import ApplyPreviewDialog from '@/components/batch/ApplyPreviewDialog.vue'

describe('ApplyPreviewDialog', () => {
  it('loads preview on open and shows counts', async () => {
    setActivePinia(createPinia())
    vi.spyOn(api, 'fetchBatchJob').mockResolvedValue({ id: 'j1' } as never)
    vi.spyOn(api, 'fetchBatchItems').mockResolvedValue([] as never)
    vi.spyOn(api, 'previewApply').mockResolvedValue({
      to_create: 12, duplicate_skip: 1, target_folder_id: 'f1',
    })
    const { useBatchReviewStore } = await import('@/store/batchReview')
    const store = useBatchReviewStore()
    store.jobId = 'j1'

    const w = mount(ApplyPreviewDialog, {
      props: { modelValue: true, itemIds: ['i1'] },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    expect(w.text()).toContain('12')
    expect(w.text()).toContain('1 份内容重复')
  })
})
