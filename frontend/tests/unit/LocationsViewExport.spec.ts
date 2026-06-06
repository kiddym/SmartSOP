import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

vi.mock('@/api/locations', () => ({
  listLocations: vi.fn().mockResolvedValue([]),
  createLocation: vi.fn(),
  updateLocation: vi.fn(),
  deleteLocation: vi.fn(),
}))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/vendors', () => ({ listVendorsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/customers', () => ({ listCustomersMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))

const { exportLocations } = vi.hoisted(() => ({ exportLocations: vi.fn() }))
vi.mock('@/api/exports', () => ({ exportLocations }))

import LocationsView from '@/views/maindata/LocationsView.vue'

describe('LocationsView 导出 CSV 按钮', () => {
  it('点击导出按钮调用 exportLocations', async () => {
    setActivePinia(createPinia())
    const wrapper = mount(LocationsView, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text().includes('导出 CSV'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(exportLocations).toHaveBeenCalled()
  })
})
