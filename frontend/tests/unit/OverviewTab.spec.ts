import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { sa, st, ap, dp } = vi.hoisted(() => ({
  sa: vi.fn(),
  st: vi.fn(),
  ap: vi.fn(),
  dp: vi.fn(),
}))
vi.mock('@/api/workOrders', () => ({
  setAssignees: sa,
  setTeams: st,
  attachProcedure: ap,
  detachProcedure: dp,
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))
vi.mock('@/api/teams', () => ({
  listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]),
}))
vi.mock('@/api/assets', () => ({
  listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]),
}))
vi.mock('@/api/locations', () => ({
  listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]),
}))
vi.mock('@/api/procedures', () => ({
  listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]),
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import OverviewTab from '@/components/workorder/OverviewTab.vue'
import type { WorkOrderRead } from '@/types/workOrder'

const wo: WorkOrderRead = {
  id: 'w1',
  custom_id: 'WO-001',
  title: '泵检修',
  description: '检修描述',
  status: 'OPEN',
  priority: 'HIGH',
  due_date: null,
  asset_id: 'a1',
  location_id: 'l1',
  primary_user_id: 'u1',
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

function mountTab(workOrder = wo) {
  return mount(OverviewTab, {
    props: { workOrder },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  sa.mockReset().mockResolvedValue(wo)
  st.mockReset().mockResolvedValue(wo)
  ap.mockReset().mockResolvedValue(wo)
  dp.mockReset().mockResolvedValue(wo)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('OverviewTab', () => {
  it('渲染基本信息 + 资产/负责人名', async () => {
    const w = mountTab()
    await flushPromises()
    expect(w.text()).toContain('检修描述')
    expect(w.text()).toContain('泵')
    expect(w.text()).toContain('张三')
  })

  it('保存指派调 setAssignees + setTeams', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.assigneeIds = ['u1']
    vm.teamIds = ['t1']
    await vm.saveAssignment()
    await flushPromises()
    expect(sa).toHaveBeenCalledWith('w1', { user_ids: ['u1'] })
    expect(st).toHaveBeenCalledWith('w1', { team_ids: ['t1'] })
  })

  it('挂接 SOP 调 attachProcedure', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.selectedProcedure = 'pr1'
    await vm.doAttach()
    await flushPromises()
    expect(ap).toHaveBeenCalledWith('w1', { procedure_id: 'pr1' })
  })

  it('doDetach 确认后调 detachProcedure', async () => {
    const w = mountTab({ ...wo, procedure_id: 'pr1' } as WorkOrderRead)
    await flushPromises()
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    await (w.vm as any).doDetach()
    await flushPromises()
    expect(dp).toHaveBeenCalledWith('w1')
  })
})
