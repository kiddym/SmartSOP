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

import WorkOrderCategoryManageDialog from '@/components/maintenance/WorkOrderCategoryManageDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lc.mockReset().mockResolvedValue([
    { id: 'c1', name: '常规', description: '' },
    { id: 'c2', name: '紧急', description: '' },
  ])
  cc.mockReset().mockResolvedValue({})
  uc.mockReset().mockResolvedValue({})
  dc.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrderCategoryManageDialog', () => {
  it('可见时加载并渲染分类', async () => {
    mount(WorkOrderCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(lc).toHaveBeenCalled()
    expect(document.body.textContent).toContain('常规')
    expect(document.body.textContent).toContain('紧急')
  })

  it('无权限隐藏新增分类按钮', async () => {
    authState.can = false
    mount(WorkOrderCategoryManageDialog, {
      props: { visible: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const addBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '新增分类',
    )
    expect(addBtn).toBeFalsy()
  })

  it('新增提交并 emit changed', async () => {
    const w = mount(WorkOrderCategoryManageDialog, {
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
    input.value = '预防'
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cc).toHaveBeenCalledWith({ name: '预防', description: '' })
    expect(w.emitted('changed')).toBeTruthy()
  })
})
