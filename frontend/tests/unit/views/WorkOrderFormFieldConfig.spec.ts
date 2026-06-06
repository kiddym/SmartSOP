import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { cw, uw } = vi.hoisted(() => ({ cw: vi.fn(), uw: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ createWorkOrder: cw, updateWorkOrder: uw }))
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
vi.mock('@/api/workOrderCategories', () => ({
  listWorkOrderCategories: vi.fn().mockResolvedValue([{ id: 'c1', name: '常规' }]),
}))

const fc = vi.hoisted(() => ({ getFieldConfig: vi.fn(), putFieldConfig: vi.fn() }))
vi.mock('@/api/fieldConfigurations', () => fc)

import WorkOrderFormDialog from '@/components/workorder/WorkOrderFormDialog.vue'

beforeEach(() => {
  setActivePinia(createPinia())
  cw.mockReset().mockResolvedValue({ id: 'w9' })
  uw.mockReset().mockResolvedValue({})
})
afterEach(() => {
  document.body.innerHTML = ''
})

function mountDialog() {
  return mount(WorkOrderFormDialog, {
    props: { visible: true, mode: 'create', editing: null },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('WorkOrderFormDialog 字段配置应用', () => {
  it('location 配置为 visible=false 时不渲染位置字段', async () => {
    fc.getFieldConfig.mockReset().mockResolvedValue([
      { field_name: 'description', visible: true, required: false, sort_order: 0 },
      { field_name: 'asset', visible: true, required: false, sort_order: 3 },
      { field_name: 'location', visible: false, required: false, sort_order: 4 },
    ])
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as { fieldVisible: Record<string, boolean> }
    expect(vm.fieldVisible.location).toBe(false)
    const dialogText = document.querySelector('.el-dialog')?.textContent ?? ''
    expect(dialogText).not.toContain('请选择位置')
    expect(dialogText).toContain('请选择资产')
    w.unmount()
  })

  it('category 配置为 visible=false 时不渲染分类字段', async () => {
    fc.getFieldConfig.mockReset().mockResolvedValue([
      { field_name: 'category', visible: false, required: false, sort_order: 7 },
    ])
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as { fieldVisible: Record<string, boolean> }
    expect(vm.fieldVisible.category).toBe(false)
    const dialogText = document.querySelector('.el-dialog')?.textContent ?? ''
    expect(dialogText).not.toContain('请选择分类')
    w.unmount()
  })

  it('加载配置失败时降级为全部可见', async () => {
    fc.getFieldConfig.mockReset().mockRejectedValue(new Error('boom'))
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as { fieldVisible: Record<string, boolean> }
    expect(vm.fieldVisible.location).toBe(true)
    expect(vm.fieldVisible.category).toBe(true)
    expect(vm.fieldVisible.description).toBe(true)
    w.unmount()
  })

  it('必填且可见字段未填写时阻断提交', async () => {
    fc.getFieldConfig.mockReset().mockResolvedValue([
      { field_name: 'asset', visible: true, required: true, sort_order: 3 },
    ])
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as { form: { title: string } }
    vm.form.title = '泵检修'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    // asset 必填但未选，应阻断 createWorkOrder
    expect(cw).not.toHaveBeenCalled()
    w.unmount()
  })
})
