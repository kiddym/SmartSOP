import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { cw, uw } = vi.hoisted(() => ({ cw: vi.fn(), uw: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ createWorkOrder: cw, updateWorkOrder: uw }))
vi.mock('@/api/assets', () => ({
  listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]),
}))
vi.mock('@/api/locations', () => ({
  listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]),
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))
vi.mock('@/api/teams', () => ({
  listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]),
}))
vi.mock('@/api/procedures', () => ({
  listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]),
}))
vi.mock('@/api/workOrderCategories', () => ({
  listWorkOrderCategories: vi.fn().mockResolvedValue([{ id: 'c1', name: '常规' }]),
}))
vi.mock('@/api/fieldConfigurations', () => ({
  getFieldConfig: vi.fn().mockResolvedValue([]),
  putFieldConfig: vi.fn(),
}))

import WorkOrderFormDialog from '@/components/workorder/WorkOrderFormDialog.vue'
import type { WorkOrderRead } from '@/types/workOrder'

beforeEach(() => {
  setActivePinia(createPinia())
  cw.mockReset().mockResolvedValue({ id: 'w9' })
  uw.mockReset().mockResolvedValue({})
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrderFormDialog', () => {
  it('create 提交调 createWorkOrder 带 title + emit saved', async () => {
    const w = mount(WorkOrderFormDialog, {
      props: { visible: true, mode: 'create', editing: null },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.title = '泵检修'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cw).toHaveBeenCalled()
    expect(cw.mock.calls[0][0]).toMatchObject({ title: '泵检修' })
    expect(w.emitted('saved')).toBeTruthy()
  })

  it('edit 提交调 updateWorkOrder(id, 基本字段)', async () => {
    const editing: WorkOrderRead = {
      id: 'w1',
      custom_id: 'WO-001',
      title: '原标题',
      description: '',
      status: 'OPEN',
      priority: 'HIGH',
      due_date: null,
      asset_id: null,
      location_id: null,
      primary_user_id: null,
      procedure_id: null,
      procedure_group_id: null,
      completed_at: null,
      category_id: null,
      created_by_user_id: null,
      signature_url: null,
      required_signature: false,
      assignee_ids: [],
      team_ids: [],
      custom_values: {},
    }
    const w = mount(WorkOrderFormDialog, {
      props: { visible: true, mode: 'edit', editing },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.title = '新标题'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(uw).toHaveBeenCalled()
    expect(uw.mock.calls[0][0]).toBe('w1')
    expect(uw.mock.calls[0][1]).toMatchObject({ title: '新标题' })
    expect(uw.mock.calls[0][1]).not.toHaveProperty('assignee_ids')
    expect(uw.mock.calls[0][1]).not.toHaveProperty('team_ids')
    expect(uw.mock.calls[0][1]).not.toHaveProperty('procedure_id')
  })

  it('create 模式空标题点保存 → warning 且不调 createWorkOrder', async () => {
    const { ElMessage } = await import('element-plus')
    const warnSpy = vi.spyOn(ElMessage, 'warning')
    const w = mount(WorkOrderFormDialog, {
      props: { visible: true, mode: 'create', editing: null },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    // 不填 title，直接点保存
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cw).not.toHaveBeenCalled()
    expect(warnSpy).toHaveBeenCalled()
    w.unmount()
  })
})
