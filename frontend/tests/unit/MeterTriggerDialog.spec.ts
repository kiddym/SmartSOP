import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ct, ut } = vi.hoisted(() => ({ ct: vi.fn(), ut: vi.fn() }))
vi.mock('@/api/meters', () => ({ createTrigger: ct, updateTrigger: ut }))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))
vi.mock('@/api/teams', () => ({
  listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]),
}))
vi.mock('@/api/procedures', () => ({
  listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]),
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import MeterTriggerDialog from '@/components/maintenance/MeterTriggerDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  ct.mockReset().mockResolvedValue({})
  ut.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MeterTriggerDialog', () => {
  it('新增提交调 createTrigger 带 meterId + 字段', async () => {
    const w = mount(MeterTriggerDialog, {
      props: { visible: true, meterId: 'm1', editing: null },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.name = '高温触发'
    vm.form.comparator = 'MORE_THAN'
    vm.form.threshold = '80'
    vm.form.title = '降温处理'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ct).toHaveBeenCalled()
    expect(ct.mock.calls[0][0]).toBe('m1')
    expect(ct.mock.calls[0][1]).toMatchObject({
      name: '高温触发',
      comparator: 'MORE_THAN',
      threshold: '80',
      title: '降温处理',
    })
    expect(w.emitted('saved')).toBeTruthy()
  })

  it('编辑模式提交调 updateTrigger', async () => {
    const editing = {
      id: 't1',
      meter_id: 'm1',
      name: '高温',
      comparator: 'MORE_THAN',
      threshold: '80',
      is_armed: true,
      is_enabled: true,
      priority: 'HIGH',
      title: '降温',
      description: '',
      primary_user_id: null,
      procedure_id: null,
      last_triggered_at: null,
      last_work_order_id: null,
      assignee_ids: [],
      team_ids: [],
    }
    const w = mount(MeterTriggerDialog, {
      props: { visible: true, meterId: 'm1', editing: editing as any },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const vm = w.vm as any
    vm.form.threshold = '90'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ut).toHaveBeenCalled()
    expect(ut.mock.calls[0][0]).toBe('m1')
    expect(ut.mock.calls[0][1]).toBe('t1')
    expect(ut.mock.calls[0][2]).toMatchObject({ threshold: '90' })
  })
})
