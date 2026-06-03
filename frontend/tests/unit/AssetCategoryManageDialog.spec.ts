import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lac, cac, uac, dac } = vi.hoisted(() => ({
  lac: vi.fn(),
  cac: vi.fn(),
  uac: vi.fn(),
  dac: vi.fn(),
}))
const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/api/assetCategories', () => ({
  listAssetCategories: lac,
  createAssetCategory: cac,
  updateAssetCategory: uac,
  deleteAssetCategory: dac,
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can }),
}))

import AssetCategoryManageDialog from '@/components/maindata/AssetCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
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

  it('编辑提交并 emit changed', async () => {
    const w = mount(AssetCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    // 第一行（泵）的「编辑」按钮
    const editBtn = Array.from(document.querySelectorAll('.el-table .el-button')).find(
      (b) => b.textContent?.trim() === '编辑',
    ) as HTMLElement
    editBtn.click()
    await flushPromises()
    const input = document.querySelector(
      '.el-dialog input[placeholder="请输入分类名称"]',
    ) as HTMLInputElement
    // 回填：初始值应为该行原名
    expect(input.value).toBe('泵')
    input.value = '泵站'
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(uac).toHaveBeenCalledWith('c1', { name: '泵站' })
    expect(w.emitted('changed')).toBeTruthy()
  })

  it('删除并 emit changed', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mount(AssetCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const delBtn = Array.from(document.querySelectorAll('.el-table .el-button')).find(
      (b) => b.textContent?.trim() === '删除',
    ) as HTMLElement
    delBtn.click()
    await flushPromises()
    expect(dac).toHaveBeenCalledWith('c1')
    expect(w.emitted('changed')).toBeTruthy()
  })

  it('无权限时隐藏新增/编辑/删除', async () => {
    authState.can = false
    mount(AssetCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const addBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '新增分类',
    )
    expect(addBtn).toBeUndefined()
    const editBtn = Array.from(document.querySelectorAll('.el-table .el-button')).find(
      (b) => b.textContent?.trim() === '编辑',
    )
    const delBtn = Array.from(document.querySelectorAll('.el-table .el-button')).find(
      (b) => b.textContent?.trim() === '删除',
    )
    expect(editBtn).toBeUndefined()
    expect(delBtn).toBeUndefined()
  })
})
