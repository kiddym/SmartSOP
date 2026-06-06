import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import PartsConsumptionTab from '@/components/workorder/PartsConsumptionTab.vue'
import * as pcApi from '@/api/partConsumptions'
import * as partsApi from '@/api/parts'
import { useAuthStore } from '@/store/auth'

function grantAll() {
  const s = useAuthStore()
  s.user = {
    id: 'u1',
    email: 'a@b.com',
    name: 'A',
    company_id: 'c1',
    role_code: 'super_admin',
    permissions: [],
  } as never
}

describe('PartsConsumptionTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    grantAll()
  })

  it('加载消耗与备件并渲染合计', async () => {
    vi.spyOn(partsApi, 'listPartsMini').mockResolvedValue([
      { id: 'p1', name: '螺栓', custom_id: 'PRT0001' },
    ])
    vi.spyOn(pcApi, 'listPartConsumptions').mockResolvedValue([
      {
        id: 'pc1',
        part_id: 'p1',
        work_order_id: 'wo1',
        quantity: '2',
        unit_cost: '5.00',
        total_cost: '10.00',
        consumed_by_user_id: null,
        consumed_at: '2026-06-06T00:00:00Z',
      },
    ])
    const w = mount(PartsConsumptionTab, {
      props: { workOrderId: 'wo1' },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    expect(w.text()).toContain('PRT0001 螺栓')
    expect(w.text()).toContain('10.00')
  })

  it('提交登记调用 consumePart 并刷新', async () => {
    vi.spyOn(partsApi, 'listPartsMini').mockResolvedValue([
      { id: 'p1', name: '螺栓', custom_id: 'PRT0001' },
    ])
    const listSpy = vi.spyOn(pcApi, 'listPartConsumptions').mockResolvedValue([])
    const consumeSpy = vi.spyOn(pcApi, 'consumePart').mockResolvedValue({
      id: 'pc1',
      part_id: 'p1',
      work_order_id: 'wo1',
      quantity: '3',
      unit_cost: '5.00',
      total_cost: '15.00',
      consumed_by_user_id: null,
      consumed_at: '2026-06-06T00:00:00Z',
    })
    const w = mount(PartsConsumptionTab, {
      props: { workOrderId: 'wo1' },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    await w.find('[data-test="add-consumption"]').trigger('click')
    await flushPromises()
    // 直接驱动组件内部表单
    const vm = w.vm as unknown as { form: { part_id: string; quantity: string }; submit: () => Promise<void> }
    vm.form.part_id = 'p1'
    vm.form.quantity = '3'
    await vm.submit()
    await flushPromises()
    expect(consumeSpy).toHaveBeenCalledWith('wo1', { part_id: 'p1', quantity: '3' })
    expect(listSpy).toHaveBeenCalledTimes(2) // 初始 + 提交后刷新
  })
})
