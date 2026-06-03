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
const { gt, exp } = vi.hoisted(() => ({ gt: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getTrendAnalytics: gt, exportAnalytics: exp }))

import TrendsPanel from '@/views/analytics/panels/TrendsPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  granularity: 'day',
  buckets: [
    {
      bucket_start: '2026-01-01',
      work_orders_created: 3,
      work_orders_completed: 2,
      requests_received: 5,
      requests_resolved: 4,
    },
  ],
}

function mountPanel() {
  return mount(TrendsPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gt.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('TrendsPanel', () => {
  it('加载默认 day 粒度并调端点', async () => {
    mountPanel()
    await flushPromises()
    expect(gt).toHaveBeenCalledWith({
      date_from: '2026-01-01',
      date_to: '2026-03-31',
      granularity: 'day',
    })
  })

  it('切换周粒度重拉 granularity=week', async () => {
    const w = mountPanel()
    await flushPromises()
    gt.mockClear()
    const vm = w.vm as any
    vm.granularity = 'week'
    await vm.fetch()
    await flushPromises()
    expect(gt).toHaveBeenCalledWith({
      date_from: '2026-01-01',
      date_to: '2026-03-31',
      granularity: 'week',
    })
  })

  it('导出按钮调 exportAnalytics(trends, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('trends')
  })
})
