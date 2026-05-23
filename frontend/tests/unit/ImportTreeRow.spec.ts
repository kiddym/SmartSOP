import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImportTreeRow from '@/components/import-v2/ImportTreeRow.vue'

const baseProps = {
  node: {
    id: 'x', title: '范围说明', content_type: 'chapter' as const, rich_content: '',
    skip_numbering: false, mark_status: 'unmarked' as const, confidence_tier: 'high' as const,
    children: [],
  },
  depth: 1,
  level: 2,
  number: '1.1',
  selected: false,
  mode: 'normal' as const,
  checked: false,
}

describe('ImportTreeRow', () => {
  it('章节行显示层级 tag（二级）和编号', () => {
    const w = mount(ImportTreeRow, { props: baseProps })
    expect(w.text()).toContain('二级')
    expect(w.text()).toContain('1.1')
    expect(w.text()).toContain('范围说明')
  })

  it('content 节点显示 [正文] tag', () => {
    const w = mount(ImportTreeRow, {
      props: { ...baseProps, node: { ...baseProps.node, content_type: 'content' }, level: 3 },
    })
    expect(w.text()).toContain('正文')
    expect(w.text()).not.toContain('三级')
  })

  it('mark_status=review 显示 [待确认] tag', () => {
    const w = mount(ImportTreeRow, {
      props: { ...baseProps, node: { ...baseProps.node, mark_status: 'review' } },
    })
    expect(w.text()).toContain('待确认')
  })

  it('mark_status=step 显示 [→步骤] 徽章', () => {
    const w = mount(ImportTreeRow, {
      props: { ...baseProps, node: { ...baseProps.node, mark_status: 'step' } },
    })
    expect(w.text()).toContain('→步骤')
  })

  it('点击行触发 select 事件', async () => {
    const w = mount(ImportTreeRow, { props: baseProps })
    await w.trigger('click')
    expect(w.emitted('select')).toBeTruthy()
  })

  it('layer-marking 模式显示 checkbox', () => {
    const w = mount(ImportTreeRow, { props: { ...baseProps, mode: 'layer-marking' } })
    expect(w.find('.tr-check').exists()).toBe(true)
  })

  it('normal 模式不显示 checkbox', () => {
    const w = mount(ImportTreeRow, { props: baseProps })
    expect(w.find('.tr-check').exists()).toBe(false)
  })
})
