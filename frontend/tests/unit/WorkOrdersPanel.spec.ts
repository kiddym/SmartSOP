import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/components/analytics/BaseChart.vue', () => ({
  default: {
    name: 'BaseChart',
    props: ['option', 'height'],
    template: '<div class="chart-stub" />',
  },
}))
const { gwo, exp } = vi.hoisted(() => ({ gwo: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getWorkOrderAnalytics: gwo, exportAnalytics: exp }))
vi.mock('@/api/assets', () => ({
  listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]),
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))

import WorkOrdersPanel from '@/views/analytics/panels/WorkOrdersPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  total: 42,
  by_status: { OPEN: 10, IN_PROGRESS: 5, COMPLETE: 25, ON_HOLD: 1, CANCELED: 1 },
  by_priority: { HIGH: 8, MEDIUM: 20, LOW: 10, NONE: 4 },
  completed: 25,
  completion_rate: 0.595,
  overdue: 3,
  avg_cycle_time_hours: 48.5,
  avg_response_time_hours: 6.2,
  by_asset: [{ asset_id: 'a1', user_id: null, category_id: null, count: 12 }],
  by_user: [{ asset_id: null, user_id: 'u1', category_id: null, count: 15 }],
  by_category: [],
}

function mountPanel(params = { date_from: '2026-01-01', date_to: '2026-03-31' }) {
  return mount(WorkOrdersPanel, {
    props: { baseParams: params },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gwo.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrdersPanel', () => {
  it('加载并渲染 KPI（总数/逾期）', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gwo).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31' })
    expect(w.text()).toContain('42')
    expect(w.text()).toContain('3')
  })

  it('baseParams 变更触发重拉', async () => {
    const w = mountPanel()
    await flushPromises()
    gwo.mockClear()
    await w.setProps({
      baseParams: { date_from: '2026-02-01', date_to: '2026-02-28', asset_id: 'a1' },
    })
    await flushPromises()
    expect(gwo).toHaveBeenCalledWith({
      date_from: '2026-02-01',
      date_to: '2026-02-28',
      asset_id: 'a1',
    })
  })

  it('导出按钮调 exportAnalytics(work-orders, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(exp).toHaveBeenCalled()
    expect(exp.mock.calls[0][0]).toBe('work-orders')
  })
})
