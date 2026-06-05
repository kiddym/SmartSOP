import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return { ...actual, ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm' as never) } }
})

const { lc, cc, uc, dc } = vi.hoisted(() => ({ lc: vi.fn(), cc: vi.fn(), uc: vi.fn(), dc: vi.fn() }))
vi.mock('@/api/costCategories', () => ({
  listCostCategories: lc,
  createCostCategory: cc,
  updateCostCategory: uc,
  deleteCostCategory: dc,
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import { ElMessageBox } from 'element-plus'
import CostCategoryManageDialog from '@/components/workorder/CostCategoryManageDialog.vue'

function mountDialog() {
  return mount(CostCategoryManageDialog, {
    props: { visible: true },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lc.mockReset().mockResolvedValue([{ id: 'c1', name: '差旅费', description: '出差相关费用' }])
  cc.mockReset().mockResolvedValue({})
  uc.mockReset().mockResolvedValue({})
  dc.mockReset().mockResolvedValue(undefined)
  vi.mocked(ElMessageBox.confirm).mockReset().mockResolvedValue('confirm' as never)
})
afterEach(() => { document.body.innerHTML = '' })

describe('CostCategoryManageDialog', () => {
  it('visible 时加载并渲染分类', async () => {
    const w = mountDialog()
    await flushPromises()
    expect(lc).toHaveBeenCalled()
    expect(w.text()).toContain('差旅费')
    expect(w.text()).toContain('出差相关费用')
  })

  it('新增提交携带 name + description', async () => {
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as {
      openCreate: () => void
      form: { name: string; description: string }
      submitForm: () => Promise<void>
    }
    vm.openCreate()
    vm.form.name = '材料费'
    vm.form.description = '原材料采购'
    await vm.submitForm()
    expect(cc).toHaveBeenCalledWith({ name: '材料费', description: '原材料采购' })
  })

  it('编辑回填并提交 update', async () => {
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as {
      openEdit: (r: { id: string; name: string; description: string }) => void
      form: { name: string; description: string }
      submitForm: () => Promise<void>
    }
    vm.openEdit({ id: 'c1', name: '差旅费', description: '出差相关费用' })
    expect(vm.form.name).toBe('差旅费')
    expect(vm.form.description).toBe('出差相关费用')
    await vm.submitForm()
    expect(uc).toHaveBeenCalledWith('c1', expect.objectContaining({ name: '差旅费' }))
  })

  it('删除确认后调用 delete', async () => {
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as { handleDelete: (r: { id: string; name: string }) => Promise<void> }
    await vm.handleDelete({ id: 'c1', name: '差旅费' })
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(dc).toHaveBeenCalledWith('c1')
  })

  it('无 manage 权限隐藏新增按钮', async () => {
    authState.can = false
    const w = mountDialog()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新增分类')).toBeFalsy()
  })
})
