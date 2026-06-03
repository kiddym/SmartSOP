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
const { gr, exp } = vi.hoisted(() => ({ gr: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getRequestAnalytics: gr, exportAnalytics: exp }))

import RequestsPanel from '@/views/analytics/panels/RequestsPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  total: 30,
  by_status: { PENDING: 5, APPROVED: 20, REJECTED: 3, CANCELED: 2 },
  by_priority: { HIGH: 6, MEDIUM: 15, LOW: 7, NONE: 2 },
  received: 30,
  resolved: 25,
  converted: 20,
  avg_resolution_cycle_hours: 12.3,
}

function mountPanel() {
  return mount(RequestsPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gr.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('RequestsPanel', () => {
  it('加载并渲染 KPI（总数/解决/转工单）', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gr).toHaveBeenCalled()
    expect(w.text()).toContain('30')
    expect(w.text()).toContain('25')
    expect(w.text()).toContain('20')
  })

  it('导出按钮调 exportAnalytics(requests, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('requests')
  })
})
