import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lc, cc, uc, dc } = vi.hoisted(() => ({
  lc: vi.fn(),
  cc: vi.fn(),
  uc: vi.fn(),
  dc: vi.fn(),
}))
vi.mock('@/api/customers', () => ({
  listCustomers: lc,
  createCustomer: cc,
  updateCustomer: uc,
  deleteCustomer: dc,
}))
vi.mock('@/api/parts', () => ({ listPartsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import CustomersView from '@/views/inventory/CustomersView.vue'

function mountView() {
  return mount(CustomersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lc.mockReset().mockResolvedValue([
    {
      id: 'c1',
      name: '甲方公司',
      customer_type: '大客户',
      description: '',
      rate: '5',
      billing_currency: 'CNY',
      address: '上海',
      phone: '021-222',
      email: 'b@c.com',
      website: '',
      part_ids: [],
      asset_ids: [],
      location_ids: [],
    },
  ])
  cc.mockReset().mockResolvedValue({})
  uc.mockReset().mockResolvedValue({})
  dc.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('CustomersView', () => {
  it('加载并渲染客户行（含结算货币）', async () => {
    const w = mountView()
    await flushPromises()
    expect(lc).toHaveBeenCalled()
    expect(w.text()).toContain('甲方公司')
    expect(w.text()).toContain('CNY')
  })

  it('新建提交携带 name + billing_currency', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建客户')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '乙方'
    nameInput.dispatchEvent(new Event('input'))
    const currencyInput = document.querySelector(
      '.el-dialog input[placeholder="如 CNY / USD"]',
    ) as HTMLInputElement
    currencyInput.value = 'USD'
    currencyInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cc).toHaveBeenCalled()
    expect(cc.mock.calls[0][0]).toMatchObject({ name: '乙方', billing_currency: 'USD' })
  })

  it('无权限隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建客户')).toBeFalsy()
  })
})
