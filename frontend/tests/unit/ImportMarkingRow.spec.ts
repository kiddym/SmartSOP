import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ElementPlus from 'element-plus'
import ImportMarkingRow from '@/components/import-v2/ImportMarkingRow.vue'

const base = { label: '目的', role: 'chapter_1' as const, indent: 0 }

describe('ImportMarkingRow', () => {
  it('渲染四个级别选项 + 文本', () => {
    const w = mount(ImportMarkingRow, { props: base })
    const t = w.text()
    expect(t).toContain('一级')
    expect(t).toContain('二级')
    expect(t).toContain('三级')
    expect(t).toContain('正文')
    expect(t).toContain('目的')
  })

  it('点击某级别 → emit set（需真实 Element Plus）', async () => {
    const w = mount(ImportMarkingRow, { props: base, global: { plugins: [ElementPlus] } })
    const inners = w.findAll('.el-radio-button__inner')
    expect(inners.length).toBe(4)
    await w.find('input[value="content"]').setValue(true) // 正文
    expect(w.emitted('set')?.[0]).toEqual(['content'])
  })

  it('缩进随 indent 变化（indent*16+8 px）', () => {
    const w = mount(ImportMarkingRow, { props: { ...base, indent: 2 } })
    expect((w.find('.mr').element as HTMLElement).style.paddingLeft).toBe('40px')
  })

  it('初始选中与 role prop 一致（受控，非 v-model）', () => {
    const w = mount(ImportMarkingRow, {
      props: { ...base, role: 'chapter_2' as const },
      global: { plugins: [ElementPlus] },
    })
    const checked = w.find('input[value="chapter_2"]').element as HTMLInputElement
    expect(checked.checked).toBe(true)
  })

  it('选择章节级别也 emit 对应 role', async () => {
    const w = mount(ImportMarkingRow, { props: base, global: { plugins: [ElementPlus] } })
    await w.find('input[value="chapter_3"]').setValue(true)
    expect(w.emitted('set')?.[0]).toEqual(['chapter_3'])
  })
})

describe('ImportMarkingRow disableContent', () => {
  it('disableContent=true 时「正文」单选被禁用', () => {
    const w = mount(ImportMarkingRow, {
      props: { label: 'X', role: 'chapter_1', indent: 0, disableContent: true },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('input[value="content"]').attributes('disabled')).toBeDefined()
  })
  it('默认不禁用「正文」', () => {
    const w = mount(ImportMarkingRow, {
      props: { label: 'X', role: 'chapter_1', indent: 0 },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('input[value="content"]').attributes('disabled')).toBeUndefined()
  })
})
