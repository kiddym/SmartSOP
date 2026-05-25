import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ImportSideRail from '@/components/import-v2/ImportSideRail.vue'

describe('ImportSideRail', () => {
  it('渲染传入的 label', () => {
    const w = mount(ImportSideRail, { props: { label: 'Word 原文预览', side: 'left' } })
    expect(w.text()).toContain('Word 原文预览')
  })

  it('左侧 rail 展开箭头为 »', () => {
    const w = mount(ImportSideRail, { props: { label: 'X', side: 'left' } })
    expect(w.get('.rail-expand').text()).toBe('»')
  })

  it('右侧 rail 展开箭头为 «', () => {
    const w = mount(ImportSideRail, { props: { label: 'X', side: 'right' } })
    expect(w.get('.rail-expand').text()).toBe('«')
  })

  it('点击竖条 emit expand', async () => {
    const w = mount(ImportSideRail, { props: { label: 'X', side: 'left' } })
    await w.get('.rail').trigger('click')
    expect(w.emitted('expand')).toHaveLength(1)
  })

  it('title 提示包含 label', () => {
    const w = mount(ImportSideRail, { props: { label: 'Word 原文预览', side: 'left' } })
    expect(w.get('.rail').attributes('title')).toBe('展开Word 原文预览')
  })
})
