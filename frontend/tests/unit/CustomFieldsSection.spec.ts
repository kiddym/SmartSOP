import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'

// ── api mock (hoisted so vi.mock factory can use it) ───────
const api = vi.hoisted(() => ({ listCustomFields: vi.fn() }))
vi.mock('@/api/customFields', () => api)

import CustomFieldsSection from '@/components/CustomFieldsSection.vue'

const DEFS = [
  {
    id: '1',
    entity_type: 'work_order',
    key: 'note',
    name: '备注',
    field_type: 'text',
    description: '',
    required: false,
    default_value: null,
    options: [],
    validation_rules: {},
    sort_order: 0,
    status: 'active',
  },
  {
    id: '2',
    entity_type: 'work_order',
    key: 'sev',
    name: '严重度',
    field_type: 'select',
    description: '',
    required: false,
    default_value: null,
    options: [
      { value: 'high', label: '高' },
      { value: 'low', label: '低' },
    ],
    validation_rules: {},
    sort_order: 1,
    status: 'active',
  },
]

beforeEach(() => {
  api.listCustomFields.mockReset()
  api.listCustomFields.mockResolvedValue(DEFS)
})

function mountSection(props: Record<string, unknown> = {}) {
  return mount(CustomFieldsSection, {
    props: {
      entityType: 'work_order',
      modelValue: {},
      ...props,
    },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('CustomFieldsSection', () => {
  it('挂载后调用 listCustomFields 并渲染两个字段标签', async () => {
    const w = mountSection()
    await flushPromises()

    expect(api.listCustomFields).toHaveBeenCalledWith('work_order')

    // field labels should appear
    expect(w.text()).toContain('备注')
    expect(w.text()).toContain('严重度')
  })

  it('渲染 text 字段的 el-input 控件', async () => {
    const w = mountSection()
    await flushPromises()

    // At least one input element exists (text field)
    const inputs = w.findAll('input')
    expect(inputs.length).toBeGreaterThan(0)
  })

  it('修改 text 输入触发 update:modelValue，包含新值', async () => {
    const w = mountSection({ modelValue: {} })
    await flushPromises()

    // Find the text input (not the select's hidden input)
    // ElInput renders a visible <input> element
    const textInput = w.find('input[type="text"], input:not([readonly])')
    expect(textInput.exists()).toBe(true)

    await textInput.setValue('x')
    await flushPromises()

    const emitted = w.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    const lastPayload = (emitted as unknown[][])[(emitted as unknown[][]).length - 1][0] as Record<string, unknown>
    expect(lastPayload.note).toBe('x')
  })

  it('readonly=true 时不渲染输入控件，显示字段值与 select 的 label', async () => {
    const w = mountSection({
      readonly: true,
      modelValue: { note: 'hello', sev: 'high' },
    })
    await flushPromises()

    // No editable inputs
    expect(w.find('input').exists()).toBe(false)

    // Values are displayed as text
    expect(w.text()).toContain('hello')
    // The select option label should be shown, not the raw value
    expect(w.text()).toContain('高')
  })

  it('defs 为空时不渲染任何内容', async () => {
    api.listCustomFields.mockResolvedValue([])
    const w = mountSection()
    await flushPromises()

    expect(w.find('.custom-fields-section').exists()).toBe(false)
  })

  it('API 失败时吞异常，组件不渲染（不阻断宿主）', async () => {
    api.listCustomFields.mockRejectedValue(new Error('网络错误'))
    const w = mountSection()
    await flushPromises()

    expect(w.find('.custom-fields-section').exists()).toBe(false)
  })

  it('entityType 变更时重新拉取', async () => {
    const w = mountSection({ entityType: 'work_order' })
    await flushPromises()
    expect(api.listCustomFields).toHaveBeenCalledTimes(1)

    await w.setProps({ entityType: 'asset' })
    await flushPromises()
    expect(api.listCustomFields).toHaveBeenCalledTimes(2)
    expect(api.listCustomFields).toHaveBeenLastCalledWith('asset')
  })

  it('multi_select readonly 时用顿号连接多个标签', async () => {
    api.listCustomFields.mockResolvedValue([
      {
        id: '3',
        entity_type: 'work_order',
        key: 'tags',
        name: '标签',
        field_type: 'multi_select',
        description: '',
        required: false,
        default_value: null,
        options: [
          { value: 'a', label: '选项A' },
          { value: 'b', label: '选项B' },
        ],
        validation_rules: {},
        sort_order: 0,
        status: 'active',
      },
    ])

    const w = mountSection({
      readonly: true,
      modelValue: { tags: ['a', 'b'] },
    })
    await flushPromises()

    expect(w.text()).toContain('选项A、选项B')
  })

  it('值为空时只读显示「—」', async () => {
    const w = mountSection({
      readonly: true,
      modelValue: {},
    })
    await flushPromises()

    expect(w.text()).toContain('—')
  })
})
