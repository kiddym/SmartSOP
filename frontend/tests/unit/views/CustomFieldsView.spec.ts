import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  listCustomFields: vi.fn(),
  createCustomField: vi.fn(),
  updateCustomField: vi.fn(),
  archiveCustomField: vi.fn(),
  restoreCustomField: vi.fn(),
  deleteCustomField: vi.fn(),
  reorderCustomFields: vi.fn(),
}))
vi.mock('@/api/customFields', () => api)

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'

const FIELDS = [
  {
    id: '1',
    entity_type: 'work_order',
    key: 'sev',
    name: '严重度',
    field_type: 'text',
    description: '',
    required: false,
    default_value: null,
    options: [],
    validation_rules: {},
    sort_order: 0,
    status: 'active',
  },
]

const ASSET_FIELDS = [
  {
    id: '2',
    entity_type: 'asset',
    key: 'serial',
    name: '序列号',
    field_type: 'text',
    description: '',
    required: false,
    default_value: null,
    options: [],
    validation_rules: {},
    sort_order: 0,
    status: 'active',
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  api.listCustomFields.mockReset().mockResolvedValue(FIELDS)
  api.createCustomField.mockReset().mockResolvedValue({ ...FIELDS[0], id: '99' })
  api.updateCustomField.mockReset().mockResolvedValue(FIELDS[0])
  api.archiveCustomField.mockReset().mockResolvedValue({ ...FIELDS[0], status: 'archived' })
  api.restoreCustomField.mockReset().mockResolvedValue(FIELDS[0])
  api.deleteCustomField.mockReset().mockResolvedValue(undefined)
  api.reorderCustomFields.mockReset().mockResolvedValue(FIELDS)
})

function mountView() {
  return mount(CustomFieldsView, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('CustomFieldsView', () => {
  it('挂载后调用 listCustomFields 并渲染字段名', async () => {
    const w = mountView()
    await flushPromises()
    expect(api.listCustomFields).toHaveBeenCalledWith('work_order', true)
    expect(w.text()).toContain('严重度')
  })

  it('切换 entity_type 后再次调用 listCustomFields', async () => {
    api.listCustomFields
      .mockResolvedValueOnce(FIELDS)       // initial load (work_order)
      .mockResolvedValueOnce(ASSET_FIELDS) // after switch to asset

    const w = mountView()
    await flushPromises()
    expect(api.listCustomFields).toHaveBeenCalledTimes(1)
    expect(api.listCustomFields).toHaveBeenLastCalledWith('work_order', true)

    // Trigger entity change by updating the component's entityType ref via vm
    const vm = w.vm as any
    vm.entityType = 'asset'
    vm.onEntityChange()
    await flushPromises()

    expect(api.listCustomFields).toHaveBeenCalledTimes(2)
    expect(api.listCustomFields).toHaveBeenLastCalledWith('asset', true)
    expect(w.text()).toContain('序列号')
  })

  it('点击新建并提交后调用 createCustomField，入参含 entity_type/key/name', async () => {
    const w = mountView()
    await flushPromises()

    // Click the 新建字段 button
    const createBtn = w.findAll('.el-button').find((b) => b.text() === '新建字段')
    expect(createBtn).toBeTruthy()
    await createBtn!.trigger('click')
    await flushPromises()

    // Fill in the form fields via vm to bypass DOM complexity
    const vm = w.vm as any
    vm.form.name = '紧急程度'
    vm.form.key = 'urgency'
    vm.form.field_type = 'text'

    await vm.submitForm()
    await flushPromises()

    expect(api.createCustomField).toHaveBeenCalledOnce()
    const callArg = api.createCustomField.mock.calls[0][0]
    expect(callArg).toMatchObject({
      entity_type: 'work_order',
      key: 'urgency',
      name: '紧急程度',
    })
  })

  it('无 company.settings 权限时「新建」按钮不渲染', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    const createBtn = w.findAll('.el-button').find((b) => b.text() === '新建字段')
    expect(createBtn).toBeFalsy()
  })
})
