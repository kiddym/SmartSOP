import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ge, ps } = vi.hoisted(() => ({ ge: vi.fn(), ps: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ getExecution: ge, patchStepResult: ps }))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can }),
}))

import ExecutionTab from '@/components/workorder/ExecutionTab.vue'
import type { ExecutionView } from '@/types/workOrder'

function makeView(): ExecutionView {
  return {
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
        input_schema: { type: 'NUMBER', unit: 'Nm' },
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
        input_schema: { type: 'CHECKBOX', options: ['A', 'B'] },
        response: { values: ['A'] },
        is_done: false,
        done_by_user_id: null,
        done_at: null,
        notes: '',
      },
      {
        id: 's3',
        node_id: 'n4',
        node_code: 'S3',
        node_sort_order: 4,
        input_schema: { type: 'COMMON' },
        response: {},
        is_done: false,
        done_by_user_id: null,
        done_at: null,
        notes: '',
      },
    ],
  }
}

function mountTab() {
  return mount(ExecutionTab, {
    props: { workOrderId: 'w1' },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  ge.mockReset().mockResolvedValue(makeView())
  ps.mockReset().mockResolvedValue(makeView())
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

  it('有 execute 权限时渲染可编辑控件与保存按钮', async () => {
    const w = mountTab()
    await flushPromises()
    // NUMBER 步骤渲染 input
    expect(w.find('.step-row[data-step="S1"] input').exists()).toBe(true)
    // CHECKBOX 步骤渲染 checkbox 组
    expect(w.find('.step-row[data-step="S2"] .el-checkbox').exists()).toBe(true)
    expect(w.text()).toContain('保存')
    expect(w.text()).toContain('标记完成')
  })

  it('修改数值并保存调 patchStepResult（response.value + notes）', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.drafts['s1'].value = 42
    vm.drafts['s1'].notes = '紧固到位'
    await vm.save(vm.exec.steps[0], null)
    await flushPromises()
    expect(ps).toHaveBeenCalledWith('w1', 's1', {
      response: { value: 42 },
      notes: '紧固到位',
    })
  })

  it('标记完成传 is_done=true', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    await vm.save(vm.exec.steps[1], true)
    await flushPromises()
    expect(ps).toHaveBeenCalledWith('w1', 's2', {
      response: { values: ['A'] },
      notes: '',
      is_done: true,
    })
  })

  it('CHECKBOX 多选保存 response.values', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.drafts['s2'].values = ['A', 'B']
    await vm.save(vm.exec.steps[1], null)
    await flushPromises()
    expect(ps).toHaveBeenCalledWith('w1', 's2', {
      response: { values: ['A', 'B'] },
      notes: '',
    })
  })

  it('COMMON 步骤保存不带 response', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    await vm.save(vm.exec.steps[2], true)
    await flushPromises()
    expect(ps).toHaveBeenCalledWith('w1', 's3', { notes: '', is_done: true })
  })

  it('无 execute 权限时只读：不渲染保存/录入控件', async () => {
    authState.can = false
    const w = mountTab()
    await flushPromises()
    expect(w.text()).not.toContain('保存')
    expect(w.text()).not.toContain('标记完成')
    expect(w.find('.step-row[data-step="S1"] input').exists()).toBe(false)
    // 仍展示已完成态与 SOP 头
    expect(w.text()).toContain('SOP-1')
    expect(w.text()).toContain('已完成')
  })
})
