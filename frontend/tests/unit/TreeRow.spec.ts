import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import TreeRow from '@/components/editor/TreeRow.vue'
import type { FlatRow } from '@/types/node'

function row(overrides: Partial<FlatRow> = {}): FlatRow {
  return {
    id: 'a',
    kind: 'chapter',
    depth: 0,
    parent_id: null,
    title: '安全须知',
    code: '1.0',
    skip_numbering: false,
    mark_status: 'unmarked',
    form_type: null,
    has_children: false,
    expanded: false,
    fallback: '(未命名章节)',
    ...overrides,
  }
}

const baseProps = {
  selected: false,
  markMode: false,
  selectedForMark: false,
  addState: { canAddChapter: true, canAddContent: true, canAddStep: true },
  editable: true,
  canMoveUp: false,
  canMoveDown: false,
  dropHint: '' as const,
}

function mountRow(r: FlatRow, extra: Record<string, unknown> = {}) {
  return mount(TreeRow, {
    props: { row: r, ...baseProps, ...extra },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('TreeRow', () => {
  it('显示 code 与标题', () => {
    const w = mountRow(row())
    expect(w.text()).toContain('1.0')
    expect(w.text()).toContain('安全须知')
  })

  it('uses border-box sizing so virtual row height stays at 30px', () => {
    const w = mountRow(row())
    expect(getComputedStyle(w.find('.tr').element).boxSizing).toBe('border-box')
  })

  it('点击行派发 select', async () => {
    const w = mountRow(row())
    await w.find('.tr').trigger('click')
    expect(w.emitted('select')).toBeTruthy()
  })

  it('三种行都渲染「＋新增」触发器', () => {
    for (const kind of ['chapter', 'content', 'step'] as const) {
      const w = mountRow(row({ id: kind, kind, code: '1.1' }))
      expect(w.text()).toContain('＋新增')
    }
  })

  it('不再渲染升级/降级符号', () => {
    const w = mountRow(row())
    expect(w.text()).not.toContain('⇤')
    expect(w.text()).not.toContain('⇥')
  })

  it('空标题「章节」显示「缺标题」标记，内容块不显示', () => {
    const wc = mountRow(row({ title: '' }))
    expect(wc.find('.tr-missing-tag').exists()).toBe(true)
    expect(wc.find('.tr--missing').exists()).toBe(true)

    const wct = mountRow(row({ id: 'x', kind: 'content', title: '', fallback: '(空内容)' }))
    expect(wct.find('.tr-missing-tag').exists()).toBe(false)
  })

  it('⋮ 触发器渲染，且其下拉 command 派发 remove', () => {
    const w = mountRow(row())
    expect(w.find('.more-trigger').exists()).toBe(true)
    // el-dropdown 的弹层经 popper 异步挂载，jsdom 不渲染；直接验证我方接线：
    // ⋮ 下拉（结构上为末个 el-dropdown）的 @command → emit('remove')。
    const dropdowns = w.findAllComponents({ name: 'ElDropdown' })
    dropdowns[dropdowns.length - 1].vm.$emit('command', 'remove')
    expect(w.emitted('remove')).toBeTruthy()
  })
})
