import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ge } = vi.hoisted(() => ({ ge: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ getExecution: ge }))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))

import ExecutionTab from '@/components/workorder/ExecutionTab.vue'

function mountTab() {
  return mount(ExecutionTab, {
    props: { workOrderId: 'w1' },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  ge.mockReset().mockResolvedValue({
    procedure: { id: 'p1', group_id: 'g1', code: 'SOP-1', name: '泵保养', version: 2 },
    outline: [
      { node_id: 'n1', heading_level: 1, kind: 'heading', body: '准备', code: 'H1', sort_order: 1 },
    ],
    steps: [
      {
        id: 's1',
        node_id: 'n2',
        node_code: 'S1',
        node_sort_order: 2,
        input_schema: {},
        response: {},
        is_done: true,
        done_by_user_id: 'u1',
        done_at: '2026-06-01T02:00:00',
        notes: '完成',
      },
      {
        id: 's2',
        node_id: 'n3',
        node_code: 'S2',
        node_sort_order: 3,
        input_schema: {},
        response: {},
        is_done: false,
        done_by_user_id: null,
        done_at: null,
        notes: '',
      },
    ],
  })
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('ExecutionTab', () => {
  it('加载执行视图 + 渲染 SOP 名 + 步骤完成态', async () => {
    const w = mountTab()
    await flushPromises()
    expect(ge).toHaveBeenCalledWith('w1')
    expect(w.text()).toContain('泵保养') // procedure name
    expect(w.text()).toContain('已完成') // is_done true tag
    expect(w.text()).toContain('未完成') // is_done false tag
    expect(w.text()).toContain('S1') // node_code
    expect(w.text()).toContain('张三') // done_by_user_id='u1' 解析为用户名
  })

  it('getExecution 失败时展示错误提示', async () => {
    const spy = vi.spyOn(ElMessage, 'error')
    ge.mockReset().mockRejectedValue(new Error('network'))
    mountTab()
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('加载执行视图失败，请重试')
  })
})
