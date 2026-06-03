import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ll, dl, st, sta, lac, dac, gcs } = vi.hoisted(() => ({
  ll: vi.fn(),
  dl: vi.fn(),
  st: vi.fn(),
  sta: vi.fn(),
  lac: vi.fn(),
  dac: vi.fn(),
  gcs: vi.fn(),
}))
vi.mock('@/api/workOrders', () => ({
  listLabor: ll,
  deleteLabor: dl,
  stopTimer: st,
  startTimer: sta,
  createLabor: vi.fn(),
  updateLabor: vi.fn(),
  listAdditionalCosts: lac,
  deleteAdditionalCost: dac,
  createAdditionalCost: vi.fn(),
  updateAdditionalCost: vi.fn(),
  getCostSummary: gcs,
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))
vi.mock('@/api/timeCategories', () => ({ listTimeCategories: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/costCategories', () => ({ listCostCategories: vi.fn().mockResolvedValue([]) }))
vi.mock('@/components/workorder/LaborDialog.vue', () => ({
  default: {
    name: 'LaborDialog',
    props: ['visible', 'workOrderId', 'editing'],
    emits: ['update:visible', 'saved'],
    template: '<div class="labor-dialog-stub" />',
  },
}))
vi.mock('@/components/workorder/AdditionalCostDialog.vue', () => ({
  default: {
    name: 'AdditionalCostDialog',
    props: ['visible', 'workOrderId', 'editing'],
    emits: ['update:visible', 'saved'],
    template: '<div class="cost-dialog-stub" />',
  },
}))
vi.mock('@/components/analytics/KpiCard.vue', () => ({
  default: {
    name: 'KpiCard',
    props: ['label', 'value', 'unit', 'hint'],
    template: '<div class="kpi-stub">{{ label }}:{{ value }}</div>',
  },
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import LaborCostTab from '@/components/workorder/LaborCostTab.vue'

function mountTab() {
  return mount(LaborCostTab, {
    props: { workOrderId: 'w1' },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  ll.mockReset().mockResolvedValue([
    {
      id: 'l1',
      work_order_id: 'w1',
      user_id: 'u1',
      time_category_id: null,
      started_at: null,
      stopped_at: '2026-06-01T01:00:00',
      duration_seconds: 3600,
      hourly_rate: '50.00',
      notes: '',
      running: false,
      cost: '50.00',
      running_elapsed_seconds: null,
    },
  ])
  dl.mockReset().mockResolvedValue(undefined)
  st.mockReset().mockResolvedValue({})
  sta.mockReset().mockResolvedValue({})
  lac.mockReset().mockResolvedValue([
    {
      id: 'c1',
      work_order_id: 'w1',
      cost_category_id: null,
      title: '运费',
      amount: '100.00',
      description: '',
      created_by_user_id: null,
    },
  ])
  dac.mockReset().mockResolvedValue(undefined)
  gcs.mockReset().mockResolvedValue({
    labor_total: '50.00',
    additional_total: '100.00',
    parts_total: '0.00',
    total: '150.00',
  })
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('LaborCostTab', () => {
  it('加载成本汇总 + 工时 + 额外成本', async () => {
    const w = mountTab()
    await flushPromises()
    expect(ll).toHaveBeenCalledWith('w1')
    expect(lac).toHaveBeenCalledWith('w1')
    expect(gcs).toHaveBeenCalledWith('w1')
    expect(w.text()).toContain('150.00') // total
    expect(w.text()).toContain('张三') // labor user
    expect(w.text()).toContain('运费') // additional cost title
  })

  it('删除工时调 deleteLabor 并重取汇总', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    await vm.removeLabor({ id: 'l1' })
    await flushPromises()
    expect(dl).toHaveBeenCalledWith('w1', 'l1')
    expect(gcs).toHaveBeenCalledTimes(2) // 初次 + 删后重取
  })

  it('开始计时调 startTimer 并触发 reloadAll', async () => {
    const w = mountTab()
    await flushPromises()
    const callsBefore = gcs.mock.calls.length
    await (w.vm as any).handleStartTimer()
    await flushPromises()
    expect(sta).toHaveBeenCalledWith('w1')
    expect(gcs.mock.calls.length).toBeGreaterThan(callsBefore)
  })

  it('停止计时调 stopTimer 并传正确参数', async () => {
    const w = mountTab()
    await flushPromises()
    await (w.vm as any).handleStopTimer({ id: 'l1' })
    await flushPromises()
    expect(st).toHaveBeenCalledWith('w1', 'l1')
  })

  it('删除成本调 deleteAdditionalCost 并传正确参数', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountTab()
    await flushPromises()
    await (w.vm as any).removeCost({ id: 'c1' })
    await flushPromises()
    expect(dac).toHaveBeenCalledWith('w1', 'c1')
  })
})
