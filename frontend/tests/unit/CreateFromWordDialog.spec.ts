import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const { importFromWord } = vi.hoisted(() => ({ importFromWord: vi.fn() }))
const { fetchFolderTree } = vi.hoisted(() => ({ fetchFolderTree: vi.fn() }))
vi.mock('@/api/parse', () => ({ importFromWord }))
vi.mock('@/api/folders', () => ({ fetchFolderTree }))

import CreateFromWordDialog from '@/components/CreateFromWordDialog.vue'

// el-select 的下拉在 jsdom 里惰性挂载、内部 reactive 易递归——用极简 stub 让文件夹逻辑可测。
const SelectStub = {
  name: 'ElSelect',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: '<div class="el-select-stub"><slot /></div>',
}
const OptionStub = {
  name: 'ElOption',
  props: { value: { type: String, default: '' }, label: { type: String, default: '' } },
  template: '<div class="el-option-stub">{{ label }}</div>',
}

// 关→开切换触发 watch(visible)（非 immediate）→ 走真实的 reset + loadLeaves。
async function open(): Promise<VueWrapper> {
  const wrapper = mount(CreateFromWordDialog, {
    props: { modelValue: false },
    global: {
      plugins: [ElementPlus],
      stubs: { ElSelect: SelectStub, ElOption: OptionStub, teleport: true },
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

async function pickFile(wrapper: VueWrapper, name: string): Promise<File> {
  const file = new File([new Uint8Array([1])], name)
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
  return file
}

async function setFolder(wrapper: VueWrapper, id: string): Promise<void> {
  await wrapper.findComponent(SelectStub).vm.$emit('update:modelValue', id)
}

async function clickSubmit(wrapper: VueWrapper): Promise<void> {
  const btn = wrapper.findAll('button').find((b) => b.text().includes('导入并编辑'))
  await btn?.trigger('click')
}

describe('CreateFromWordDialog', () => {
  beforeEach(() => {
    importFromWord.mockReset()
    fetchFolderTree.mockReset().mockResolvedValue([])
  })

  it('打开时仅把非系统、含 prefix 的叶子文件夹填入下拉', async () => {
    fetchFolderTree.mockResolvedValue([
      { id: 'sys', full_path: '系统', system: true, prefix: 'X', children: [] },
      { id: 'f1', full_path: '根/QC', system: false, prefix: 'QC', children: [] },
      {
        id: 'mid',
        full_path: '根',
        system: false,
        prefix: '',
        children: [{ id: 'f2', full_path: '根/子', system: false, prefix: 'AB', children: [] }],
      },
    ])
    const wrapper = await open()
    // sys 系统排除；mid 非叶且无 prefix 排除 → 仅 f1、f2
    expect(wrapper.findAllComponents(OptionStub)).toHaveLength(2)
  })

  it('选文件后用文件名（去 .docx）自动填充名称', async () => {
    const wrapper = await open()
    await pickFile(wrapper, '采购控制程序.docx')
    await flushPromises()
    const nameInput = wrapper.find('input[placeholder="默认取文件名"]')
    expect((nameInput.element as HTMLInputElement).value).toBe('采购控制程序')
  })

  it('缺文件时提交：不调用 importFromWord', async () => {
    const wrapper = await open()
    await clickSubmit(wrapper)
    await flushPromises()
    expect(importFromWord).not.toHaveBeenCalled()
  })

  it('提交成功：调 importFromWord、emit imported、关闭对话框', async () => {
    importFromWord.mockResolvedValue({ id: 'p9', code: 'QC-009' })
    const wrapper = await open()
    const file = await pickFile(wrapper, '记录控制.docx')
    await setFolder(wrapper, 'f1')
    await clickSubmit(wrapper)
    await flushPromises()
    expect(importFromWord).toHaveBeenCalledWith(file, 'f1', '记录控制')
    expect(wrapper.emitted('imported')?.[0]).toEqual(['p9'])
    expect(wrapper.emitted('update:modelValue')?.some((e) => e[0] === false)).toBe(true)
  })

  it('提交失败：保持打开、不 emit imported', async () => {
    importFromWord.mockRejectedValue(new Error('PARSE_NO_HEADINGS'))
    const wrapper = await open()
    await pickFile(wrapper, 'bad.docx')
    await setFolder(wrapper, 'f1')
    await clickSubmit(wrapper)
    await flushPromises()
    expect(importFromWord).toHaveBeenCalled()
    expect(wrapper.emitted('imported')).toBeUndefined()
    expect(wrapper.emitted('update:modelValue')?.some((e) => e[0] === false)).toBeFalsy()
  })
})
