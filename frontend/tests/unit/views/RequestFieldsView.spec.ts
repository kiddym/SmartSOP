import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  getFieldConfig: vi.fn(),
  putFieldConfig: vi.fn(),
}))
vi.mock('@/api/fieldConfigurations', () => api)

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import RequestFieldsView from '@/views/settings/RequestFieldsView.vue'

const CONFIG = [
  { field_name: 'description', visible: true, required: false, sort_order: 0 },
  { field_name: 'priority', visible: true, required: true, sort_order: 1 },
  { field_name: 'due_date', visible: false, required: false, sort_order: 2 },
  { field_name: 'asset', visible: true, required: false, sort_order: 3 },
  { field_name: 'location', visible: true, required: false, sort_order: 4 },
]

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  api.getFieldConfig.mockReset().mockResolvedValue(CONFIG)
  api.putFieldConfig.mockReset().mockResolvedValue(CONFIG)
})

function mountView() {
  return mount(RequestFieldsView, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('RequestFieldsView', () => {
  it('加载并渲染字段中文名', async () => {
    const w = mountView()
    await flushPromises()
    expect(api.getFieldConfig).toHaveBeenCalledWith('REQUEST')
    expect(w.text()).toContain('描述')
    expect(w.text()).toContain('优先级')
    expect(w.text()).toContain('截止日期')
    expect(w.text()).toContain('资产')
    expect(w.text()).toContain('位置')
  })

  it('保存调用 putFieldConfig 携带字段项', async () => {
    const w = mountView()
    await flushPromises()
    const saveBtn = w.findAll('.el-button').find((b) => b.text() === '保存')
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(api.putFieldConfig).toHaveBeenCalled()
    expect(api.putFieldConfig.mock.calls[0][0]).toBe('REQUEST')
    const items = api.putFieldConfig.mock.calls[0][1]
    expect(items).toHaveLength(5)
    expect(items[0]).toMatchObject({ field_name: 'description', visible: true, required: false })
  })

  it('无 company.settings 权限时隐藏保存按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '保存')).toBeFalsy()
  })
})
