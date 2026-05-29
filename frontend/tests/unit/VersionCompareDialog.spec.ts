import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import type { Node } from '@/types/node'

const { listNodes } = vi.hoisted(() => ({ listNodes: vi.fn() }))
vi.mock('@/api/nodes', () => ({ listNodes }))

import VersionCompareDialog from '@/components/version/VersionCompareDialog.vue'

function n(over: Partial<Node>): Node {
  return {
    id: over.id ?? 'x', procedure_id: 'p', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

let wrapper: ReturnType<typeof mount> | null = null

async function mountDialog(oldNodes: Node[], newNodes: Node[]) {
  listNodes.mockImplementation((procId: string) => Promise.resolve(procId === 'old' ? oldNodes : newNodes))
  wrapper = mount(VersionCompareDialog, {
    props: { modelValue: false, oldId: 'old', newId: 'new', oldVersion: 2, newVersion: 4 },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true }) // false→true triggers the open watcher
  await flushPromises()
  return wrapper
}

describe('VersionCompareDialog', () => {
  beforeEach(() => listNodes.mockReset())
  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('fetches both trees on open and renders title + a changed row', async () => {
    await mountDialog(
      [n({ id: 'o1', code: '1', body: '<p>目的</p>' })],
      [n({ id: 'n1', code: '1', body: '<p>目的（改）</p>' }), n({ id: 'n2', code: '2', body: '<p>新章节</p>', sort_order: 1 })],
    )
    expect(listNodes).toHaveBeenCalledWith('old')
    expect(listNodes).toHaveBeenCalledWith('new')
    expect(document.body.textContent).toContain('版本对比')
    expect(document.body.textContent).toContain('v2 → v4')
    expect(document.body.textContent).toContain('新章节')
  })

  it('只看变更 (default on) hides unchanged rows', async () => {
    await mountDialog(
      [n({ id: 'o1', code: '1', body: '<p>不变标题XYZ</p>' }), n({ id: 'o2', code: '2', body: '<p>旧</p>', sort_order: 1 })],
      [n({ id: 'n1', code: '1', body: '<p>不变标题XYZ</p>' }), n({ id: 'n2', code: '2', body: '<p>新内容</p>', sort_order: 1 })],
    )
    expect(document.body.textContent).not.toContain('不变标题XYZ') // unchanged → hidden
    expect(document.body.textContent).toContain('新内容')          // modified → shown
  })

  it('fetches on mount when opened already-true (real host v-if path)', async () => {
    listNodes.mockImplementation((procId: string) =>
      Promise.resolve(procId === 'old' ? [] : [n({ id: 'n1', code: '1', body: '<p>新增章节QQ</p>' })]),
    )
    wrapper = mount(VersionCompareDialog, {
      props: { modelValue: true, oldId: 'old', newId: 'new', oldVersion: 1, newVersion: 2 },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(listNodes).toHaveBeenCalledWith('old')
    expect(listNodes).toHaveBeenCalledWith('new')
    expect(document.body.textContent).toContain('新增章节QQ') // the added node renders
  })

  it('modified row shows a char-level diff (charMode default on)', async () => {
    await mountDialog(
      [n({ id: 'o1', code: '1', body: '<p>本程序适用于公司所有股东</p>' })],
      [n({ id: 'n1', code: '1', body: '<p>本程序适用于公司创始股东</p>' })],
    )
    const line = document.body.querySelector('.vc-line') as HTMLElement // single modified row; teleported to body
    line.dispatchEvent(new MouseEvent('click', { bubbles: true }))      // expand it
    await flushPromises()
    expect(document.body.querySelector('.vc-del')?.textContent).toContain('所有')
    expect(document.body.querySelector('.vc-ins')?.textContent).toContain('创始')
    expect(document.body.querySelector('.vc-html')).toBeNull() // rendered side-by-side hidden in charMode
  })
})
