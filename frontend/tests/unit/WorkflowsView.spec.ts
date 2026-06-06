import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lw, cw, uw, dw } = vi.hoisted(() => ({
  lw: vi.fn(),
  cw: vi.fn(),
  uw: vi.fn(),
  dw: vi.fn(),
}))
vi.mock('@/api/workflows', () => ({
  listWorkflows: lw,
  createWorkflow: cw,
  updateWorkflow: uw,
  deleteWorkflow: dw,
}))
vi.mock('@/api/workOrderCategories', () => ({
  listWorkOrderCategories: vi.fn().mockResolvedValue([{ id: 'cat1', name: '机械', description: '' }]),
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))
vi.mock('@/api/teams', () => ({
  listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组', member_ids: [] }]),
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import WorkflowsView from '@/views/settings/WorkflowsView.vue'

function mountView() {
  return mount(WorkflowsView, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

const wf1 = {
  id: 'w1',
  name: '高优先自动分类',
  enabled: true,
  trigger: 'WORK_ORDER_CREATED',
  conditions: [{ field: 'priority', op: 'eq', value: 'HIGH' }],
  actions: [{ type: 'set_category', value: 'cat1' }],
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lw.mockReset().mockResolvedValue([wf1])
  cw.mockReset().mockResolvedValue({})
  uw.mockReset().mockResolvedValue({})
  dw.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkflowsView', () => {
  it('加载并渲染工作流列表（名称/触发/条件数/动作数）', async () => {
    const w = mountView()
    await flushPromises()
    expect(lw).toHaveBeenCalled()
    expect(w.text()).toContain('高优先自动分类')
    expect(w.text()).toContain('工单创建时')
    // 条件数 1 / 动作数 1
    expect(w.text()).toContain('1')
  })

  it('新建提交携带 trigger + conditions + actions', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建工作流')
    await addBtn!.trigger('click')
    await flushPromises()
    const vm = w.vm as never as {
      form: {
        name: string
        trigger: string
        conditions: { field: string; op: string; value: string | null }[]
        actions: { type: string; value: string | null }[]
      }
    }
    vm.form.name = '紧急升级'
    vm.form.trigger = 'WORK_ORDER_CREATED'
    vm.form.conditions = [{ field: 'priority', op: 'eq', value: 'HIGH' }]
    vm.form.actions = [{ type: 'set_category', value: 'cat1' }]
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cw).toHaveBeenCalled()
    expect(cw.mock.calls[0][0]).toMatchObject({
      name: '紧急升级',
      trigger: 'WORK_ORDER_CREATED',
      conditions: [{ field: 'priority', op: 'eq', value: 'HIGH' }],
      actions: [{ type: 'set_category', value: 'cat1' }],
    })
  })

  it('停用切换调 updateWorkflow(enabled=false)', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as never as { toggleEnabled: (r: typeof wf1) => Promise<void> }
    await vm.toggleEnabled(wf1)
    await flushPromises()
    expect(uw).toHaveBeenCalledWith('w1', { enabled: false })
  })

  it('无 workflow.manage 隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建工作流')).toBeFalsy()
  })
})
