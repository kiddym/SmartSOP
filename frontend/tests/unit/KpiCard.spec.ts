import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import KpiCard from '@/components/analytics/KpiCard.vue'

describe('KpiCard', () => {
  it('渲染 label/value/unit/hint', () => {
    const w = mount(KpiCard, {
      props: { label: '完成率', value: '85.0', unit: '%', hint: '近90天' },
      global: { plugins: [ElementPlus] },
    })
    expect(w.text()).toContain('完成率')
    expect(w.text()).toContain('85.0')
    expect(w.text()).toContain('%')
    expect(w.text()).toContain('近90天')
  })
})
