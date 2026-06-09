import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lt, ct, ut, dt } = vi.hoisted(() => ({
  lt: vi.fn(),
  ct: vi.fn(),
  ut: vi.fn(),
  dt: vi.fn(),
}))
vi.mock('@/api/timeCategories', () => ({
  listTimeCategories: lt,
  createTimeCategory: ct,
  updateTimeCategory: ut,
  deleteTimeCategory: dt,
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

import TimeCategoryManagePanel from '@/components/workorder/TimeCategoryManagePanel.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  confirmMock.mockReset().mockResolvedValue('confirm')
  lt.mockReset().mockResolvedValue([
    { id: '1', name: '正常工时', description: '', hourly_rate: '0' },
  ])
  ct.mockReset().mockResolvedValue({})
  ut.mockReset().mockResolvedValue({})
  dt.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('TimeCategoryManagePanel', () => {
  it('挂载即加载工时分类列表', async () => {
    mount(TimeCategoryManagePanel, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lt).toHaveBeenCalled()
    expect(document.body.textContent).toContain('正常工时')
  })

  it('新增提交并 emit changed', async () => {
    const wrapper = mount(TimeCategoryManagePanel, {
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
    input.value = '加班工时'
    input.dispatchEvent(new Event('input'))
    await flushPromises()

    // Click the "保存" button to submit the form
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    expect(saveBtn).toBeTruthy()
    saveBtn.click()
    await flushPromises()

    expect(ct).toHaveBeenCalledWith({ name: '加班工时', hourly_rate: '0', description: '' })
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('删除确认后调用 deleteTimeCategory 并 emit changed', async () => {
    const wrapper = mount(TimeCategoryManagePanel, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()

    // Click the "删除" button in the table
    const deleteBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '删除',
    ) as HTMLElement
    expect(deleteBtn).toBeTruthy()
    deleteBtn.click()
    await flushPromises()

    expect(confirmMock).toHaveBeenCalled()
    expect(dt).toHaveBeenCalledWith('1')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })
})
