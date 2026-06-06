import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── router mocks ───────────────────────────────────────────
const push = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'a1' } }),
  useRouter: () => ({ push }),
}))

// ── api mocks ──────────────────────────────────────────────
const { ga } = vi.hoisted(() => ({ ga: vi.fn() }))
vi.mock('@/api/assets', () => ({ getAsset: ga }))
vi.mock('@/api/assetCategories', () => ({
  listAssetCategories: vi.fn().mockResolvedValue([{ id: 'c1', name: '泵类' }]),
}))
vi.mock('@/api/locations', () => ({
  listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '总部', custom_id: 'L-1' }]),
}))
vi.mock('@/api/vendors', () => ({
  listVendorsMini: vi.fn().mockResolvedValue([{ id: 'v1', name: '供应商甲' }]),
}))
vi.mock('@/api/customers', () => ({
  listCustomersMini: vi.fn().mockResolvedValue([{ id: 'cu1', name: '客户乙' }]),
}))
vi.mock('@/api/parts', () => ({
  listPartsMini: vi.fn().mockResolvedValue([{ id: 'p1', name: '备件丙', custom_id: 'P-1' }]),
}))
const { lwo } = vi.hoisted(() => ({ lwo: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ listWorkOrders: lwo }))
const { lm } = vi.hoisted(() => ({ lm: vi.fn() }))
vi.mock('@/api/meters', () => ({ listMeters: lm }))
const { gd, pd, dd } = vi.hoisted(() => ({ gd: vi.fn(), pd: vi.fn(), dd: vi.fn() }))
vi.mock('@/api/deprecations', () => ({
  getDeprecation: gd,
  putDeprecation: pd,
  deleteDeprecation: dd,
}))
// EntityAttachments 内部依赖附件 api；stub 掉避免噪音。
vi.mock('@/components/EntityAttachments.vue', () => ({
  default: { name: 'EntityAttachments', template: '<div class="stub-attachments" />' },
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true }),
}))

import AssetDetailView from '@/views/maindata/AssetDetailView.vue'

const ASSET = {
  id: 'a1',
  custom_id: 'A-001',
  name: '泵 1',
  description: '主泵描述',
  parent_id: null,
  location_id: 'l1',
  category_id: 'c1',
  status: 'OPERATIONAL',
  serial_number: 'SN-9',
  model: 'X100',
  manufacturer: '制造商甲',
  power: '5kW',
  warranty_expiration_date: null,
  in_service_date: null,
  acquisition_cost: null,
  barcode: null,
  nfc_id: null,
  primary_user_id: null,
  area: '库区A',
  additional_infos: '附加文本',
  image_url: '/img/a1',
  assigned_user_ids: [],
  team_ids: [],
  vendor_ids: ['v1'],
  customer_ids: ['cu1'],
  part_ids: ['p1'],
}

function mountView() {
  return mount(AssetDetailView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  push.mockReset()
  ga.mockReset().mockResolvedValue({ ...ASSET })
  lwo.mockReset().mockResolvedValue([
    {
      id: 'w1',
      custom_id: 'WO-1',
      title: '检修工单',
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
  lm.mockReset().mockResolvedValue([
    {
      id: 'm1',
      custom_id: 'M-1',
      name: '温度表',
      unit: '℃',
      update_frequency_days: 7,
      asset_id: 'a1',
      location_id: null,
      meter_category_id: null,
      image_url: null,
      user_ids: [],
    },
  ])
  gd.mockReset().mockResolvedValue({
    id: 'd1',
    asset_id: 'a1',
    purchase_price: '1000.00',
    purchase_date: '2024-01-01',
    residual_value: '100.00',
    useful_life_years: 5,
    rate: null,
    current_value: '720.00',
  })
  pd.mockReset().mockResolvedValue({
    id: 'd1',
    asset_id: 'a1',
    purchase_price: '2000.00',
    purchase_date: '2024-01-01',
    residual_value: '100.00',
    useful_life_years: 5,
    rate: null,
    current_value: '1620.00',
  })
  dd.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('AssetDetailView', () => {
  it('详情 tab 渲染资产字段与映射名称', async () => {
    const w = mountView()
    await flushPromises()
    expect(ga).toHaveBeenCalledWith('a1')
    expect(w.text()).toContain('A-001')
    expect(w.text()).toContain('泵 1')
    expect(w.text()).toContain('制造商甲')
    expect(w.text()).toContain('X100')
    expect(w.text()).toContain('SN-9')
    expect(w.text()).toContain('库区A')
    expect(w.text()).toContain('泵类') // 分类映射
    expect(w.text()).toContain('总部') // 位置映射
    expect(w.text()).toContain('供应商甲') // vendor 映射
    expect(w.text()).toContain('客户乙') // customer 映射
  })

  it('工单 tab 调 listWorkOrders({asset_id}) 反查并可跳转', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.loadWorkOrders()
    await flushPromises()
    expect(lwo).toHaveBeenCalledWith({ asset_id: 'a1' })
    expect(vm.workOrders).toHaveLength(1)
    expect(vm.workOrders[0].custom_id).toBe('WO-1')
  })

  it('备件 tab 由 part_ids 映射出 custom_id/name 只读列表', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.relatedParts).toEqual([{ id: 'p1', custom_id: 'P-1', name: '备件丙' }])
  })

  it('计量 tab 调 listMeters({asset_id}) 反查', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.loadMeters()
    await flushPromises()
    expect(lm).toHaveBeenCalledWith({ asset_id: 'a1' })
    expect(vm.meters[0].name).toBe('温度表')
  })

  it('折旧 tab 加载并保存调 putDeprecation upsert', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.loadDeprecation()
    await flushPromises()
    expect(gd).toHaveBeenCalledWith('a1')
    expect(vm.depForm.purchase_price).toBe('1000.00')
    expect(vm.deprecation.current_value).toBe('720.00')
    vm.depForm.purchase_price = '2000.00'
    await vm.saveDeprecation()
    await flushPromises()
    expect(pd).toHaveBeenCalled()
    expect(pd.mock.calls[0][0]).toBe('a1')
    expect(pd.mock.calls[0][1]).toMatchObject({ purchase_price: '2000.00' })
    expect(vm.deprecation.current_value).toBe('1620.00')
  })
})
