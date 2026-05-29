import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import NodeTreeRow from '@/components/editor/NodeTreeRow.vue'
import type { TreeRow } from '@/utils/nodeTree'
import type { Node } from '@/types/node'

function node(over: Partial<Node>): Node {
  return {
    id: 'a', procedure_id: 'p', sort_order: 0, heading_level: 1, kind: 'node',
    body: '<p>章节</p>', code: '1', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}
function treeRow(over: Partial<Node> = {}, row: Partial<TreeRow> = {}): TreeRow {
  const nd = node(over)
  return { node: nd, title: '章节', hasChildren: false, expanded: true, ...row }
}

const baseProps = { selected: false, selectedForMark: false, dropHint: '' as const }
function mountRow(row: TreeRow, extra: Record<string, unknown> = {}) {
  return mount(NodeTreeRow, {
    props: { row, ...baseProps, ...extra },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('NodeTreeRow', () => {
  it('renders code + title', () => {
    const w = mountRow(treeRow({}, { title: '安全须知' }))
    expect(w.text()).toContain('1')
    expect(w.text()).toContain('安全须知')
  })

  it('indents by node.depth (depth 2 → paddingLeft 38px)', () => {
    const w = mountRow(treeRow({ depth: 2 }))
    expect((w.find('.ntr').element as HTMLElement).style.paddingLeft).toBe('38px')
  })

  it('click emits select; caret emits toggle', async () => {
    const w = mountRow(treeRow({}, { hasChildren: true }))
    await w.find('.ntr').trigger('click')
    expect(w.emitted('select')).toBeTruthy()
    await w.find('.ntr-caret').trigger('click')
    expect(w.emitted('toggle')).toBeTruthy()
  })

  it('chip dropdown command l2 emits chip("l2"); step emits chip("step")', async () => {
    const w = mountRow(treeRow())
    const dd = w.findComponent({ name: 'ElDropdown' })
    dd.vm.$emit('command', 'l2')
    dd.vm.$emit('command', 'step')
    expect(w.emitted('chip')).toEqual([['l2'], ['step']])
  })

  it('delete button emits remove', async () => {
    const w = mountRow(treeRow())
    await w.find('.ntr-del').trigger('click')
    expect(w.emitted('remove')).toBeTruthy()
  })

  it('checkbox emits check with shift flag', async () => {
    const w = mountRow(treeRow())
    await w.find('.ntr-check').trigger('click')
    expect(w.emitted('check')).toBeTruthy()
  })

  it('review node renders 待确认 badge', () => {
    const w = mountRow(treeRow({ mark_status: 'review' }))
    expect(w.find('.ntr-review').exists()).toBe(true)
  })

  it('dragstart/dragover/drop/dragend are forwarded', async () => {
    const w = mountRow(treeRow())
    await w.find('.ntr').trigger('dragstart')
    await w.find('.ntr').trigger('dragover')
    await w.find('.ntr').trigger('drop')
    await w.find('.ntr').trigger('dragend')
    expect(w.emitted('dragstart')).toBeTruthy()
    expect(w.emitted('dragover')).toBeTruthy()
    expect(w.emitted('drop')).toBeTruthy()
    expect(w.emitted('dragend')).toBeTruthy()
  })
})

describe('NodeTreeRow — readonly', () => {
  it('hides checkbox / chip / delete and is not draggable when readonly', () => {
    const w = mountRow(treeRow(), { readonly: true })
    expect(w.find('.ntr-check').exists()).toBe(false)
    expect(w.findComponent({ name: 'ElDropdown' }).exists()).toBe(false)
    expect(w.find('.ntr-del').exists()).toBe(false)
    expect((w.find('.ntr').element as HTMLElement).getAttribute('draggable')).toBe('false')
  })

  it('still shows code + title + review badge when readonly', () => {
    const w = mountRow(treeRow({ mark_status: 'review' }, { title: '安全须知' }), { readonly: true })
    expect(w.text()).toContain('安全须知')
    expect(w.find('.ntr-review').exists()).toBe(true)
  })
})

describe('NodeTreeRow — indeterminate', () => {
  it('passes indeterminate to the checkbox (aria-checked="mixed" on label)', () => {
    const w = mountRow(treeRow({ heading_level: 1 }, { hasChildren: true }), { indeterminate: true })
    // Element Plus renders indeterminate as aria-checked="mixed" on the <label> wrapper
    // and is-indeterminate on the inner .el-checkbox__input span (not the label).
    expect(w.find('.ntr-check').attributes('aria-checked')).toBe('mixed')
  })
})

describe('NodeTreeRow — Tab indent', () => {
  it('Tab on the row emits indent "in"; Shift+Tab emits "out"', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }))
    await w.find('.ntr').trigger('keydown', { key: 'Tab' })
    expect(w.emitted('indent')?.[0]).toEqual(['in'])
    await w.find('.ntr').trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(w.emitted('indent')?.[1]).toEqual(['out'])
  })
  it('Tab from an inner control (checkbox) does not emit indent', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }))
    await w.find('.ntr-check').trigger('keydown', { key: 'Tab' })
    expect(w.emitted('indent')).toBeFalsy()
  })
  it('readonly row: not focusable, no indent', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }), { readonly: true })
    expect(w.find('.ntr').attributes('tabindex')).toBeUndefined()
    await w.find('.ntr').trigger('keydown', { key: 'Tab' })
    expect(w.emitted('indent')).toBeFalsy()
  })
  it('non-readonly row is click-focusable (tabindex -1)', () => {
    const w = mountRow(treeRow({ heading_level: 1 }))
    expect(w.find('.ntr').attributes('tabindex')).toBe('-1')
  })
})
