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
const { gar, exp } = vi.hoisted(() => ({ gar: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getAssetReliabilityAnalytics: gar, exportAnalytics: exp }))
vi.mock('@/api/assetCategories', () => ({
  listAssetCategories: vi.fn().mockResolvedValue([{ id: 'ac1', name: '泵类' }]),
}))

import AssetReliabilityPanel from '@/views/analytics/panels/AssetReliabilityPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  window_hours: 2160,
  assets: [
    {
      asset_id: 'a1',
      custom_id: 'AS-001',
      name: '主泵',
      availability_pct: 97.5,
      downtime_count: 2,
      total_downtime_hours: 54,
      mttr_hours: 27,
      mtbf_hours: 1053,
      total_maintenance_cost: '1500.00',
      acquisition_cost: '50000.00',
      cost_to_value_ratio: 0.03,
    },
  ],
  fleet_availability_pct: 97.5,
  fleet_total_downtime_hours: 54,
  fleet_mttr_hours: 27,
  fleet_mtbf_hours: 1053,
  fleet_total_maintenance_cost: '1500.00',
}

function mountPanel() {
  return mount(AssetReliabilityPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gar.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('AssetReliabilityPanel', () => {
  it('加载并渲染车队 KPI + 资产表（MTTR/MTBF）', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gar).toHaveBeenCalled()
    expect(w.text()).toContain('主泵')
    expect(w.text()).toContain('AS-001')
    expect(w.text()).toContain('27')
    expect(w.text()).toContain('1053')
  })

  it('导出按钮调 exportAnalytics(asset-reliability, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('asset-reliability')
  })

  it('选中资产分类后 buildParams 叠加 category_id', async () => {
    const w = mountPanel()
    await flushPromises()
    gar.mockClear()
    const vm = w.vm as any
    vm.categoryId = 'ac1'
    await vm.fetch()
    await flushPromises()
    expect(gar).toHaveBeenCalledWith({
      date_from: '2026-01-01',
      date_to: '2026-03-31',
      category_id: 'ac1',
    })
  })
})
