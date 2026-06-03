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
const { gc, exp } = vi.hoisted(() => ({ gc: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getCostAnalytics: gc, exportAnalytics: exp }))
vi.mock('@/api/assets', () => ({
  listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]),
}))
vi.mock('@/api/vendors', () => ({
  listVendorsMini: vi.fn().mockResolvedValue([{ id: 'v1', name: '一号供应商' }]),
}))

import CostsPanel from '@/views/analytics/panels/CostsPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  parts_consumption_cost: '1200.00',
  consumption_by_part: [
    { part_id: 'p1', custom_id: 'P-001', name: '轴承', qty: '10', cost: '500.00' },
  ],
  consumption_by_asset: [{ asset_id: 'a1', cost: '500.00' }],
  po_spend_approved: '3000.00',
  po_spend_by_vendor: [{ vendor_id: 'v1', spend: '3000.00' }],
  labor_cost: '800.00',
  additional_cost: '200.00',
  total_maintenance_cost: '2200.00',
  maintenance_cost_by_asset: [
    {
      asset_id: 'a1',
      parts_cost: '500.00',
      labor_cost: '800.00',
      additional_cost: '200.00',
      total: '1500.00',
    },
  ],
}

function mountPanel() {
  return mount(CostsPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gc.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('CostsPanel', () => {
  it('加载并渲染 KPI + 备件消耗明细表', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gc).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31' })
    expect(w.text()).toContain('2200.00')
    expect(w.text()).toContain('轴承')
  })

  it('导出按钮调 exportAnalytics(costs, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp).toHaveBeenCalledWith('costs', { date_from: '2026-01-01', date_to: '2026-03-31' })
  })
})
