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
const { gi, exp } = vi.hoisted(() => ({ gi: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getInventoryAnalytics: gi, exportAnalytics: exp }))
vi.mock('@/api/partCategories', () => ({
  listPartCategories: vi.fn().mockResolvedValue([{ id: 'pc1', name: '轴承类' }]),
}))

import InventoryPanel from '@/views/analytics/panels/InventoryPanel.vue'

const data = {
  total_inventory_value: '99999.00',
  inventory_value_by_category: [{ category_id: 'pc1', name: '轴承类', value: '60000.00' }],
  low_stock_count: 4,
  low_stock_items: [
    {
      part_id: 'p1',
      custom_id: 'P-001',
      name: '深沟球轴承',
      quantity: '3',
      min_quantity: '5',
      shortfall: '2',
    },
  ],
  top_consumed_parts: [{ part_id: 'p1', custom_id: 'P-001', name: '深沟球轴承', qty: '40' }],
  abc_classification: [
    {
      part_id: 'p1',
      custom_id: 'P-001',
      name: '深沟球轴承',
      consumption_value: '8000.00',
      cumulative_pct: 80,
      abc_class: 'A',
    },
  ],
  abc_summary: { A: 1, B: 0, C: 0 },
  consumption_by_wo_category: [
    { category_id: 'wc1', name: '机械维修', cost: '30000.00', qty: '15.0000' },
    { category_id: null, name: null, cost: '12000.00', qty: '4.0000' },
  ],
  consumption_monthly_trend: [
    { month: '2026-02', cost: '10000.00' },
    { month: '2026-03', cost: '13000.00' },
  ],
}

function mountPanel(
  params: Record<string, string | undefined> = { date_from: '2026-01-01', date_to: '2026-03-31' },
) {
  return mount(InventoryPanel, {
    props: { baseParams: params },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gi.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('InventoryPanel', () => {
  it('加载并渲染 KPI（库存总值/低库存数）+ 低库存表', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gi).toHaveBeenCalled()
    expect(w.text()).toContain('99999.00')
    expect(w.text()).toContain('4')
    expect(w.text()).toContain('深沟球轴承')
  })

  it('库存端点只发 date 键（剔除 asset/location）', async () => {
    mountPanel({
      date_from: '2026-01-01',
      date_to: '2026-03-31',
      asset_id: 'a1',
      location_id: 'l1',
    })
    await flushPromises()
    expect(gi).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31' })
  })

  it('选中备件分类叠加 category_id', async () => {
    const w = mountPanel()
    await flushPromises()
    gi.mockClear()
    const vm = w.vm as any
    vm.categoryId = 'pc1'
    await vm.fetch()
    await flushPromises()
    expect(gi).toHaveBeenCalledWith({
      date_from: '2026-01-01',
      date_to: '2026-03-31',
      category_id: 'pc1',
    })
  })

  it('渲染按工单分类消耗明细（含未分类）+ 按月趋势切面', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(w.text()).toContain('按工单分类消耗成本')
    expect(w.text()).toContain('按月消耗趋势')
    // 明细表渲染分类名与未分类占位
    expect(w.text()).toContain('机械维修')
    expect(w.text()).toContain('未分类')
    expect(w.text()).toContain('30000.00')
  })

  it('导出按钮调 exportAnalytics(inventory, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('inventory')
  })
})
