import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// ── router mocks ───────────────────────────────────────────
const push = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'loc1' } }),
  useRouter: () => ({ push }),
}))

// ── api mocks ──────────────────────────────────────────────
const { gl } = vi.hoisted(() => ({ gl: vi.fn() }))
vi.mock('@/api/locations', () => ({
  getLocation: gl,
  listLocationsMini: vi
    .fn()
    .mockResolvedValue([{ id: 'p1', name: '园区', custom_id: 'L-0' }]),
}))
vi.mock('@/api/vendors', () => ({
  listVendorsMini: vi.fn().mockResolvedValue([{ id: 'v1', name: '供应商甲' }]),
}))
vi.mock('@/api/customers', () => ({
  listCustomersMini: vi.fn().mockResolvedValue([{ id: 'cu1', name: '客户乙' }]),
}))
const { la } = vi.hoisted(() => ({ la: vi.fn() }))
vi.mock('@/api/assets', () => ({ listAssets: la }))
const { lwo } = vi.hoisted(() => ({ lwo: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ listWorkOrders: lwo }))
const { lfp, cfp, dfp } = vi.hoisted(() => ({ lfp: vi.fn(), cfp: vi.fn(), dfp: vi.fn() }))
vi.mock('@/api/floorPlans', () => ({
  listFloorPlans: lfp,
  createFloorPlan: cfp,
  deleteFloorPlan: dfp,
}))
vi.mock('@/components/EntityAttachments.vue', () => ({
  default: { name: 'EntityAttachments', template: '<div class="stub-attachments" />' },
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true }),
}))

import LocationDetailView from '@/views/maindata/LocationDetailView.vue'

const LOCATION = {
  id: 'loc1',
  custom_id: 'L-001',
  name: '一号车间',
  description: '主车间描述',
  parent_id: 'p1',
  address: '工业园 12 号',
  longitude: 120.1,
  latitude: 30.2,
  image_url: '/img/loc1',
  assigned_user_ids: [],
  team_ids: [],
  vendor_ids: ['v1'],
  customer_ids: ['cu1'],
}

function mountView() {
  return mount(LocationDetailView, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  push.mockReset()
  gl.mockReset().mockResolvedValue({ ...LOCATION })
  la.mockReset().mockResolvedValue([
    {
      id: 'a1',
      custom_id: 'A-9',
      name: '泵 9',
      status: 'OPERATIONAL',
      location_id: 'loc1',
    },
  ])
  lwo.mockReset().mockResolvedValue([
    {
      id: 'w1',
      custom_id: 'WO-1',
      title: '巡检工单',
      status: 'IN_PROGRESS',
      priority: 'HIGH',
      location_id: 'loc1',
    },
  ])
  lfp.mockReset().mockResolvedValue([
    { id: 'fp1', location_id: 'loc1', name: '一层平面', image_url: null, area: '500.00' },
  ])
  cfp.mockReset().mockResolvedValue({
    id: 'fp2',
    location_id: 'loc1',
    name: '二层平面',
    image_url: null,
    area: '300.00',
  })
  dfp.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('LocationDetailView', () => {
  it('详情 tab 渲染位置字段与映射名称', async () => {
    const w = mountView()
    await flushPromises()
    expect(gl).toHaveBeenCalledWith('loc1')
    expect(w.text()).toContain('一号车间')
    expect(w.text()).toContain('L-001')
    expect(w.text()).toContain('工业园 12 号')
    expect(w.text()).toContain('园区') // 父位置映射
    expect(w.text()).toContain('供应商甲') // vendor 映射
    expect(w.text()).toContain('客户乙') // customer 映射
  })

  it('资产 tab 调 listAssets({location_id}) 反查并可跳转资产详情', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.loadAssets()
    await flushPromises()
    expect(la).toHaveBeenCalledWith({ location_id: 'loc1' })
    expect(vm.assets).toHaveLength(1)
    expect(vm.assets[0].custom_id).toBe('A-9')
  })

  it('工单 tab 调 listWorkOrders({location_id}) 反查', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.loadWorkOrders()
    await flushPromises()
    expect(lwo).toHaveBeenCalledWith({ location_id: 'loc1' })
    expect(vm.workOrders[0].custom_id).toBe('WO-1')
  })

  it('平面图 tab 列出并新增调 createFloorPlan(POST)', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.loadFloorPlans()
    await flushPromises()
    expect(lfp).toHaveBeenCalledWith('loc1')
    expect(vm.floorPlans).toHaveLength(1)
    expect(vm.floorPlans[0].name).toBe('一层平面')

    vm.fpForm.name = '二层平面'
    vm.fpForm.area = 300
    await vm.submitFloorPlan()
    await flushPromises()
    expect(cfp).toHaveBeenCalled()
    expect(cfp.mock.calls[0][0]).toBe('loc1')
    expect(cfp.mock.calls[0][1]).toMatchObject({ name: '二层平面', area: 300 })
    // 新增后重新拉取列表
    expect(lfp).toHaveBeenCalledTimes(2)
  })
})
