import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lpc, cpc, upc, dpc } = vi.hoisted(() => ({
  lpc: vi.fn(),
  cpc: vi.fn(),
  upc: vi.fn(),
  dpc: vi.fn(),
}))
vi.mock('@/api/purchaseOrderCategories', () => ({
  listPurchaseOrderCategories: lpc,
  createPurchaseOrderCategory: cpc,
  updatePurchaseOrderCategory: upc,
  deletePurchaseOrderCategory: dpc,
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import PurchaseOrderCategoryManageDialog from '@/components/inventory/PurchaseOrderCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lpc.mockReset().mockResolvedValue([
    { id: 'c1', name: '常规采购', description: '' },
    { id: 'c2', name: '紧急采购', description: '' },
  ])
  cpc.mockReset().mockResolvedValue({})
  upc.mockReset().mockResolvedValue({})
  dpc.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PurchaseOrderCategoryManageDialog', () => {
  it('可见时加载并渲染分类', async () => {
    mount(PurchaseOrderCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lpc).toHaveBeenCalled()
    expect(document.body.textContent).toContain('常规采购')
    expect(document.body.textContent).toContain('紧急采购')
  })

  it('新增提交并 emit changed', async () => {
    const w = mount(PurchaseOrderCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const addBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '新增分类',
    ) as HTMLElement
    addBtn.click()
    await flushPromises()
    const input = document.querySelector(
      '.el-dialog input[placeholder="请输入分类名称"]',
    ) as HTMLInputElement
    input.value = '备件采购'
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cpc).toHaveBeenCalledWith({ name: '备件采购', description: '' })
    expect(w.emitted('changed')).toBeTruthy()
  })
})
