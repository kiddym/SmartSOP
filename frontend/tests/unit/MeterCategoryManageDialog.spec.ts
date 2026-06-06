import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lmc, cmc, umc, dmc } = vi.hoisted(() => ({
  lmc: vi.fn(),
  cmc: vi.fn(),
  umc: vi.fn(),
  dmc: vi.fn(),
}))
const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/api/meterCategories', () => ({
  listMeterCategories: lmc,
  createMeterCategory: cmc,
  updateMeterCategory: umc,
  deleteMeterCategory: dmc,
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can }),
}))

import MeterCategoryManageDialog from '@/components/maintenance/MeterCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lmc.mockReset().mockResolvedValue([
    { id: 'c1', name: '温度', description: '温度类' },
    { id: 'c2', name: '压力', description: null },
  ])
  cmc.mockReset().mockResolvedValue({})
  umc.mockReset().mockResolvedValue({})
  dmc.mockReset().mockResolvedValue(undefined)
})

// el-dialog 通过 teleport 挂到 document.body，跨用例残留会干扰 querySelector，手动清空。
afterEach(() => {
  document.body.innerHTML = ''
})

describe('MeterCategoryManageDialog', () => {
  it('可见时加载并渲染分类（含描述）', async () => {
    mount(MeterCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lmc).toHaveBeenCalled()
    expect(document.body.textContent).toContain('温度')
    expect(document.body.textContent).toContain('压力')
    expect(document.body.textContent).toContain('温度类')
  })

  it('新增提交携带 name + description 并 emit changed', async () => {
    const w = mount(MeterCategoryManageDialog, {
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
    input.value = '流量'
    input.dispatchEvent(new Event('input'))
    const desc = document.querySelector('.el-dialog textarea') as HTMLTextAreaElement
    desc.value = '流量类'
    desc.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cmc).toHaveBeenCalledWith({ name: '流量', description: '流量类' })
    expect(w.emitted('changed')).toBeTruthy()
  })

  it('编辑回填并提交 description=null（清空）', async () => {
    const w = mount(MeterCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const editBtn = Array.from(document.querySelectorAll('.el-table .el-button')).find(
      (b) => b.textContent?.trim() === '编辑',
    ) as HTMLElement
    editBtn.click()
    await flushPromises()
    const input = document.querySelector(
      '.el-dialog input[placeholder="请输入分类名称"]',
    ) as HTMLInputElement
    expect(input.value).toBe('温度')
    // 清空描述
    const desc = document.querySelector('.el-dialog textarea') as HTMLTextAreaElement
    expect(desc.value).toBe('温度类')
    desc.value = ''
    desc.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(umc).toHaveBeenCalledWith('c1', { name: '温度', description: null })
    expect(w.emitted('changed')).toBeTruthy()
  })

  it('删除并 emit changed', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mount(MeterCategoryManageDialog, {
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
    expect(dmc).toHaveBeenCalledWith('c1')
    expect(w.emitted('changed')).toBeTruthy()
  })

  it('无权限时隐藏新增/编辑/删除', async () => {
    authState.can = false
    mount(MeterCategoryManageDialog, {
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
    expect(editBtn).toBeUndefined()
  })
})
