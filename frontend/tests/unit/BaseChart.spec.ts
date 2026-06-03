import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="v-chart-stub" />' },
}))

import BaseChart from '@/components/analytics/BaseChart.vue'

describe('BaseChart', () => {
  it('挂载并接收 option 不报错', () => {
    const w = mount(BaseChart, { props: { option: { series: [] } } })
    expect(w.find('.v-chart-stub').exists()).toBe(true)
  })
})
