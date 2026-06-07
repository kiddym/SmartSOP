import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ params: { id: 'w1' } }),
}))

const { gw, tr, dwr } = vi.hoisted(() => ({ gw: vi.fn(), tr: vi.fn(), dwr: vi.fn() }))
vi.mock('@/api/workOrders', () => ({
  getWorkOrder: gw,
  transitionWorkOrder: tr,
  downloadWorkOrderReport: dwr,
}))
// 各 tab stub，隔离详情壳测试
vi.mock('@/components/workorder/OverviewTab.vue', () => ({
  default: {
    name: 'OverviewTab',
    props: ['workOrder'],
    emits: ['changed'],
    template: '<div class="overview-stub" />',
  },
}))
vi.mock('@/components/workorder/LaborCostTab.vue', () => ({
  default: {
    name: 'LaborCostTab',
    props: ['workOrderId'],
    template: '<div class="laborcost-stub" />',
  },
}))
vi.mock('@/components/workorder/ActivityTab.vue', () => ({
  default: {
    name: 'ActivityTab',
    props: ['workOrderId'],
    template: '<div class="activity-stub" />',
  },
}))
vi.mock('@/components/workorder/ExecutionTab.vue', () => ({
  default: {
    name: 'ExecutionTab',
    props: ['workOrderId'],
    template: '<div class="execution-stub" />',
  },
}))
vi.mock('@/components/workorder/WorkOrderFormDialog.vue', () => ({
  default: {
    name: 'WorkOrderFormDialog',
    props: ['visible', 'mode', 'editing'],
    emits: ['update:visible', 'saved'],
    template: '<div />',
  },
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import WorkOrderDetailView from '@/views/maintenance/WorkOrderDetailView.vue'

function mountView() {
  return mount(WorkOrderDetailView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const wo = {
  id: 'w1',
  custom_id: 'WO-001',
  title: '泵检修',
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
  assignee_ids: [],
  team_ids: [],
  custom_values: {},
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  push.mockReset()
  gw.mockReset().mockResolvedValue(wo)
  tr.mockReset().mockResolvedValue({ ...wo, status: 'IN_PROGRESS' })
  dwr.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrderDetailView', () => {
  it('加载工单 + 渲染编号标题状态', async () => {
    const w = mountView()
    await flushPromises()
    expect(gw).toHaveBeenCalledWith('w1')
    expect(w.text()).toContain('WO-001')
    expect(w.text()).toContain('泵检修')
    expect(w.text()).toContain('待处理') // OPEN
  })

  it('OPEN 显示「开始」「取消」流转按钮，点「开始」调 transition(IN_PROGRESS)', async () => {
    const w = mountView()
    await flushPromises()
    const startBtn = w.findAll('.el-button').find((b) => b.text() === '开始')
    expect(startBtn).toBeTruthy()
    expect(w.findAll('.el-button').find((b) => b.text() === '取消')).toBeTruthy()
    await startBtn!.trigger('click')
    await flushPromises()
    expect(tr).toHaveBeenCalled()
    expect(tr.mock.calls[0][0]).toBe('w1')
    expect(tr.mock.calls[0][1]).toMatchObject({ to_status: 'IN_PROGRESS' })
  })

  it('无 edit 权限时不显示流转按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '开始')).toBeFalsy()
  })

  it('点「生成 PDF 报告」调 downloadWorkOrderReport(id, custom_id)', async () => {
    const w = mountView()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text().includes('生成 PDF 报告'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(dwr).toHaveBeenCalledWith('w1', 'WO-001')
  })

  it('无 view 权限时不显示 PDF 报告按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text().includes('生成 PDF 报告'))).toBeFalsy()
  })
})
