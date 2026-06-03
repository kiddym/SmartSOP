import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lac, cac, uac, dac } = vi.hoisted(() => ({
  lac: vi.fn(),
  cac: vi.fn(),
  uac: vi.fn(),
  dac: vi.fn(),
}))
vi.mock('@/api/assetCategories', () => ({
  listAssetCategories: lac,
  createAssetCategory: cac,
  updateAssetCategory: uac,
  deleteAssetCategory: dac,
}))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))

import AssetCategoryManageDialog from '@/components/maindata/AssetCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  lac.mockReset().mockResolvedValue([
    { id: 'c1', name: '泵' },
    { id: 'c2', name: '电机' },
  ])
  cac.mockReset().mockResolvedValue({})
  uac.mockReset().mockResolvedValue({})
  dac.mockReset().mockResolvedValue(undefined)
})

// el-dialog 通过 teleport 挂到 document.body，跨用例残留会干扰 querySelector，手动清空。
afterEach(() => {
  document.body.innerHTML = ''
})

describe('AssetCategoryManageDialog', () => {
  it('可见时加载并渲染分类', async () => {
    mount(AssetCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lac).toHaveBeenCalled()
    expect(document.body.textContent).toContain('泵')
    expect(document.body.textContent).toContain('电机')
  })

  it('新增提交并 emit changed', async () => {
    const w = mount(AssetCategoryManageDialog, {
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
    input.value = '阀门'
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cac).toHaveBeenCalledWith({ name: '阀门' })
    expect(w.emitted('changed')).toBeTruthy()
  })
})
