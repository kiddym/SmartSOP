import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import DiffRejudgeCard from '@/components/batch/DiffRejudgeCard.vue'
import type { ParsedNode } from '@/types/parse'

const node: ParsedNode = {
  id: 'n1', title: '3.2 操作步骤', level: 2, order: 0, parent_id: null,
  content_type: 'chapter', rich_content: '', skip_numbering: false,
  confidence: 0.55, confidence_tier: 'medium', mark_status: 'review',
  heading_source: 'heuristic', source_style_name: null, source_numbering_pattern: null,
  children: [],
}

describe('DiffRejudgeCard', () => {
  it('shows recognized type + confidence and emits op on action', async () => {
    const w = mount(DiffRejudgeCard, { props: { node }, global: { plugins: [ElementPlus] } })
    expect(w.text()).toContain('3.2 操作步骤')
    expect(w.text()).toContain('中')
    await w.find('[data-test="to-content"]').trigger('click')
    expect(w.emitted('op')?.[0]).toEqual([{ node_id: 'n1', action: 'to_content' }])
  })

  it('emits accept op', async () => {
    const w = mount(DiffRejudgeCard, { props: { node }, global: { plugins: [ElementPlus] } })
    await w.find('[data-test="accept"]').trigger('click')
    expect(w.emitted('op')?.[0]).toEqual([{ node_id: 'n1', action: 'accept' }])
  })

  it('emits set_level op carrying level (level branch of emitOp)', async () => {
    const w = mount(DiffRejudgeCard, { props: { node }, global: { plugins: [ElementPlus] } })
    await w.find('[data-test="lvl1"]').trigger('click')
    expect(w.emitted('op')?.[0]).toEqual([{ node_id: 'n1', action: 'set_level', level: 1 }])
  })
})
