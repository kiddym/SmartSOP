import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── router mocks ───────────────────────────────────────────
const push = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'p1' } }),
  useRouter: () => ({ push }),
}))

// ── api mocks ──────────────────────────────────────────────
const { gp } = vi.hoisted(() => ({ gp: vi.fn() }))
const { lpwo } = vi.hoisted(() => ({ lpwo: vi.fn() }))
vi.mock('@/api/parts', () => ({ getPart: gp, listPartWorkOrders: lpwo }))
vi.mock('@/api/partCategories', () => ({
  listPartCategories: vi.fn().mockResolvedValue([{ id: 'c1', name: '轴承类', description: '' }]),
}))
vi.mock('@/api/assets', () => ({
  listAssetsMini: vi
    .fn()
    .mockResolvedValue([{ id: 'a1', name: '泵 1', custom_id: 'A-001' }]),
}))
vi.mock('@/api/vendors', () => ({
  listVendorsMini: vi.fn().mockResolvedValue([{ id: 'v1', name: '供应商甲' }]),
}))
vi.mock('@/api/customers', () => ({
  listCustomersMini: vi.fn().mockResolvedValue([{ id: 'cu1', name: '客户乙' }]),
}))
// EntityAttachments 内部依赖附件 api；stub 掉避免噪音。
vi.mock('@/components/EntityAttachments.vue', () => ({
  default: { name: 'EntityAttachments', template: '<div class="stub-attachments" />' },
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true }),
}))

import PartDetailView from '@/views/inventory/PartDetailView.vue'

const PART = {
  id: 'p1',
  custom_id: 'P-001',
  name: '滚珠轴承',
  description: '主轴轴承描述',
  cost: '12.50',
  quantity: '8',
  min_quantity: '10',
  unit: '个',
  barcode: 'BC-9',
  non_stock: false,
  is_low_stock: true,
  category_id: 'c1',
  area: '库区B',
  additional_infos: '附加文本',
  assignee_ids: [],
  team_ids: [],
  asset_ids: ['a1'],
  location_ids: [],
  pm_ids: [],
  vendor_ids: ['v1'],
  customer_ids: ['cu1'],
}

function mountView() {
  return mount(PartDetailView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  push.mockReset()
  gp.mockReset().mockResolvedValue({ ...PART })
  lpwo.mockReset().mockResolvedValue([
    {
      id: 'w1',
      custom_id: 'WO-1',
      title: '更换轴承工单',
      status: 'IN_PROGRESS',
      priority: 'HIGH',
      description: '',
      due_date: null,
      asset_id: 'a1',
      location_id: null,
      primary_user_id: null,
      procedure_id: null,
      procedure_group_id: null,
      completed_at: null,
      category_id: null,
      created_by_user_id: null,
      assignee_ids: [],
      team_ids: [],
    },
  ])
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PartDetailView', () => {
  it('详情 tab 渲染备件字段与映射名称', async () => {
    const w = mountView()
    await flushPromises()
    expect(gp).toHaveBeenCalledWith('p1')
    expect(w.text()).toContain('P-001')
    expect(w.text()).toContain('滚珠轴承')
    expect(w.text()).toContain('12.50') // 单价
    expect(w.text()).toContain('库区B')
    expect(w.text()).toContain('轴承类') // 分类映射
    expect(w.text()).toContain('供应商甲') // vendor 映射
    expect(w.text()).toContain('客户乙') // customer 映射
    expect(w.text()).toContain('低库存') // 低库存标签
  })

  it('工单 tab 调 listPartWorkOrders(id) 反查并可跳转', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as {
      loadWorkOrders: () => Promise<void>
      workOrders: { custom_id: string }[]
    }
    await vm.loadWorkOrders()
    await flushPromises()
    expect(lpwo).toHaveBeenCalledWith('p1')
    expect(vm.workOrders).toHaveLength(1)
    expect(vm.workOrders[0].custom_id).toBe('WO-1')
  })

  it('资产 tab 由 asset_ids 映射出 custom_id/name 只读列表', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as { relatedAssets: unknown[] }
    expect(vm.relatedAssets).toEqual([{ id: 'a1', custom_id: 'A-001', name: '泵 1' }])
  })
})
