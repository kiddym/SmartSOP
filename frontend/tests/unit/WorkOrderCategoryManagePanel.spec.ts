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
vi.mock('@/api/workOrderCategories', () => ({
  listWorkOrderCategories: lc,
  createWorkOrderCategory: cc,
  updateWorkOrderCategory: uc,
  deleteWorkOrderCategory: dc,
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

const confirmMock = vi.hoisted(() => vi.fn())
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return {
    ...actual,
    ElMessageBox: {
      ...actual.ElMessageBox,
      confirm: confirmMock,
    },
  }
})

import WorkOrderCategoryManagePanel from '@/components/maintenance/WorkOrderCategoryManagePanel.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  confirmMock.mockReset().mockResolvedValue('confirm')
  lc.mockReset().mockResolvedValue([
    { id: 'c1', name: '机械', description: '' },
    { id: 'c2', name: '电气', description: '' },
  ])
  cc.mockReset().mockResolvedValue({})
  uc.mockReset().mockResolvedValue({})
  dc.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrderCategoryManagePanel', () => {
  it('挂载即加载分类列表', async () => {
    mount(WorkOrderCategoryManagePanel, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lc).toHaveBeenCalled()
    expect(document.body.textContent).toContain('机械')
    expect(document.body.textContent).toContain('电气')
  })

  it('新增提交并 emit changed', async () => {
    const wrapper = mount(WorkOrderCategoryManagePanel, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()

    // Click the "新增分类" button to open the form dialog
    const addBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '新增分类',
    ) as HTMLElement
    expect(addBtn).toBeTruthy()
    addBtn.click()
    await flushPromises()

    // Fill in the category name input
    const input = document.querySelector(
      'input[placeholder="请输入分类名称"]',
    ) as HTMLInputElement
    expect(input).toBeTruthy()
    input.value = '预防性维护'
    input.dispatchEvent(new Event('input'))
    await flushPromises()

    // Click the "保存" button to submit the form
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    expect(saveBtn).toBeTruthy()
    saveBtn.click()
    await flushPromises()

    expect(cc).toHaveBeenCalledWith({ name: '预防性维护', description: '' })
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('删除确认后调用 deleteWorkOrderCategory 并 emit changed', async () => {
    const wrapper = mount(WorkOrderCategoryManagePanel, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()

    // Click the first "删除" button in the table
    const deleteBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '删除',
    ) as HTMLElement
    expect(deleteBtn).toBeTruthy()
    deleteBtn.click()
    await flushPromises()

    expect(confirmMock).toHaveBeenCalled()
    expect(dc).toHaveBeenCalledWith('c1')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })
})
