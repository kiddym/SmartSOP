import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import CustomFieldsView from '@/views/settings/CustomFieldsView.vue'

vi.mock('@/api/customFields', () => ({
  listCustomFields: vi.fn().mockResolvedValue([]),
  createCustomField: vi.fn(),
  updateCustomField: vi.fn(),
  archiveCustomField: vi.fn(),
  restoreCustomField: vi.fn(),
  deleteCustomField: vi.fn(),
  reorderCustomFields: vi.fn(),
}))
import { listCustomFields } from '@/api/customFields'

// ElSelect 在 jsdom 全量渲染会自触发递归更新,stub 掉它只验证显隐与加载逻辑。
const mountOpts = {
  global: { plugins: [ElementPlus], stubs: { teleport: true, ElSelect: true, ElOption: true } },
}

describe('CustomFieldsView lockedEntity', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('lockedEntity 时隐藏实体选择器与页标题,并按该实体加载', async () => {
    const wrapper = mount(CustomFieldsView, {
      props: { lockedEntity: 'asset', embedded: true },
      ...mountOpts,
    })
    await flushPromises()
    expect(wrapper.find('el-select-stub').exists()).toBe(false)
    expect(wrapper.find('.page-title').exists()).toBe(false)
    expect(listCustomFields).toHaveBeenCalledWith('asset', true)
  })

  it('无 lockedEntity 时渲染实体选择器与页标题,默认 work_order', async () => {
    const wrapper = mount(CustomFieldsView, mountOpts)
    await flushPromises()
    expect(wrapper.find('el-select-stub').exists()).toBe(true)
    expect(wrapper.find('.page-title').exists()).toBe(true)
    expect(listCustomFields).toHaveBeenCalledWith('work_order', true)
  })
})
