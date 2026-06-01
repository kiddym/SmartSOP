import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import BatchReviewRow from '@/components/batch/BatchReviewRow.vue'

const item = {
  id: 'i1', job_id: 'j1', filename: 'pump.docx', status: 'review' as const,
  content_hash: 'h', summary: { chapter_count: 8, confidence_tier: 'low', warning_count: 2 },
  review_revision: 1, error: null,
}

function mountRow(over = {}) {
  return mount(BatchReviewRow, {
    props: { item: { ...item, ...over }, selected: false },
    global: { plugins: [ElementPlus] },
  })
}

describe('BatchReviewRow', () => {
  it('renders filename, chapter count and warning badge', () => {
    const w = mountRow()
    expect(w.text()).toContain('pump.docx')
    expect(w.text()).toContain('8')
    expect(w.text()).toContain('2')
  })

  it('emits open on preview click', async () => {
    const w = mountRow()
    await w.find('[data-test="preview"]').trigger('click')
    expect(w.emitted('open')).toBeTruthy()
  })

  it('emits apply on apply click for review item', async () => {
    const w = mountRow()
    await w.find('[data-test="apply"]').trigger('click')
    expect(w.emitted('apply')).toBeTruthy()
  })
})
