import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/requests', () => ({
  listRequests: vi.fn().mockResolvedValue([]),
  getRequest: vi.fn(),
  createRequest: vi.fn().mockResolvedValue({}),
  updateRequest: vi.fn().mockResolvedValue({}),
  deleteRequest: vi.fn(),
  approveRequest: vi.fn(),
  rejectRequest: vi.fn(),
  cancelRequest: vi.fn(),
  listRequestActivities: vi.fn().mockResolvedValue([]),
  addRequestComment: vi.fn(),
}))
vi.mock('@/api/assets', () => ({
  listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]),
}))
vi.mock('@/api/locations', () => ({
  listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]),
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))
vi.mock('@/api/teams', () => ({
  listTeams: vi.fn().mockResolvedValue([{ id: 't1', name: '机修组' }]),
}))
vi.mock('@/api/procedures', () => ({
  listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]),
}))

const fc = vi.hoisted(() => ({ getFieldConfig: vi.fn(), putFieldConfig: vi.fn() }))
vi.mock('@/api/fieldConfigurations', () => fc)

vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import RequestsView from '@/views/maintenance/RequestsView.vue'

function mountView() {
  return mount(RequestsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('RequestsView 字段配置应用', () => {
  it('location 配置为 visible=false 时不渲染位置字段', async () => {
    fc.getFieldConfig.mockReset().mockResolvedValue([
      { field_name: 'description', visible: true, required: false, sort_order: 0 },
      { field_name: 'priority', visible: true, required: false, sort_order: 1 },
      { field_name: 'due_date', visible: true, required: false, sort_order: 2 },
      { field_name: 'asset', visible: true, required: false, sort_order: 3 },
      { field_name: 'location', visible: false, required: false, sort_order: 4 },
    ])
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as { openCreate: () => void; fieldVisible: Record<string, boolean> }
    vm.openCreate()
    await flushPromises()
    expect(vm.fieldVisible.location).toBe(false)
    // 创建对话框中不应出现「请选择位置」占位的字段
    const dialogText = document.querySelector('.el-dialog')?.textContent ?? ''
    expect(dialogText).not.toContain('请选择位置')
    expect(dialogText).toContain('请选择资产')
  })

  it('加载配置失败时降级为全部可见', async () => {
    fc.getFieldConfig.mockReset().mockRejectedValue(new Error('boom'))
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as { fieldVisible: Record<string, boolean> }
    expect(vm.fieldVisible.location).toBe(true)
    expect(vm.fieldVisible.description).toBe(true)
  })

  it('必填且可见字段未填写时阻断提交', async () => {
    fc.getFieldConfig.mockReset().mockResolvedValue([
      { field_name: 'asset', visible: true, required: true, sort_order: 3 },
    ])
    const requestsApi = await import('@/api/requests')
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as { openCreate: () => void }
    vm.openCreate()
    await flushPromises()
    const titleInput = document.querySelector(
      '.el-dialog input[placeholder="请输入标题"]',
    ) as HTMLInputElement
    titleInput.value = '电机异响'
    titleInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    // asset 必填但未选，应阻断 createRequest
    expect(requestsApi.createRequest).not.toHaveBeenCalled()
  })
})
