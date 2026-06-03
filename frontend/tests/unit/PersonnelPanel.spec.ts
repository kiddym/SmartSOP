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
const { gp, exp } = vi.hoisted(() => ({ gp: vi.fn(), exp: vi.fn() }))
vi.mock('@/api/analytics', () => ({ getPersonnelAnalytics: gp, exportAnalytics: exp }))

import PersonnelPanel from '@/views/analytics/panels/PersonnelPanel.vue'

const data = {
  date_from: '2026-01-01',
  date_to: '2026-03-31',
  users: [
    {
      user_id: 'u1',
      name: '张三',
      created_count: 10,
      completed_count: 8,
      assigned_count: 12,
      labor_hours: 40.5,
      labor_cost: '2025.00',
    },
  ],
}

function mountPanel() {
  return mount(PersonnelPanel, {
    props: { baseParams: { date_from: '2026-01-01', date_to: '2026-03-31', asset_id: 'a1' } },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gp.mockReset().mockResolvedValue(data)
  exp.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('PersonnelPanel', () => {
  it('加载并渲染人员表（只发 date 键）', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(gp).toHaveBeenCalledWith({ date_from: '2026-01-01', date_to: '2026-03-31' })
    expect(w.text()).toContain('张三')
    expect(w.text()).toContain('40.5')
    expect(w.text()).toContain('2025.00')
  })

  it('导出按钮调 exportAnalytics(personnel, params)', async () => {
    const w = mountPanel()
    await flushPromises()
    const btn = w.findAll('.el-button').find((b) => b.text() === '导出CSV')
    await btn!.trigger('click')
    expect(exp.mock.calls[0][0]).toBe('personnel')
  })
})
