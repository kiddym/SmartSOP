import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return { ...actual, ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm' as never) } }
})

const { lt, ct, ut, dt } = vi.hoisted(() => ({ lt: vi.fn(), ct: vi.fn(), ut: vi.fn(), dt: vi.fn() }))
vi.mock('@/api/timeCategories', () => ({
  listTimeCategories: lt,
  createTimeCategory: ct,
  updateTimeCategory: ut,
  deleteTimeCategory: dt,
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import { ElMessageBox } from 'element-plus'
import TimeCategoryManageDialog from '@/components/workorder/TimeCategoryManageDialog.vue'

function mountDialog() {
  return mount(TimeCategoryManageDialog, {
    props: { visible: true },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lt.mockReset().mockResolvedValue([{ id: 't1', name: '电工', hourly_rate: '50.00', description: '默认' }])
  ct.mockReset().mockResolvedValue({})
  ut.mockReset().mockResolvedValue({})
  dt.mockReset().mockResolvedValue(undefined)
  vi.mocked(ElMessageBox.confirm).mockReset().mockResolvedValue('confirm' as never)
})
afterEach(() => { document.body.innerHTML = '' })

describe('TimeCategoryManageDialog', () => {
  it('visible 时加载并渲染分类（含费率）', async () => {
    const w = mountDialog()
    await flushPromises()
    expect(lt).toHaveBeenCalled()
    expect(w.text()).toContain('电工')
    expect(w.text()).toContain('50.00')
  })

  it('新增提交携带 name + hourly_rate', async () => {
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as {
      openCreate: () => void
      form: { name: string; hourly_rate: string; description: string }
      submitForm: () => Promise<void>
    }
    vm.openCreate()
    vm.form.name = '钳工'
    vm.form.hourly_rate = '60'
    await vm.submitForm()
    expect(ct).toHaveBeenCalledWith({ name: '钳工', hourly_rate: '60', description: '' })
  })

  it('编辑回填并提交 update', async () => {
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as {
      openEdit: (r: { id: string; name: string; hourly_rate: string; description: string }) => void
      form: { name: string; hourly_rate: string }
      submitForm: () => Promise<void>
    }
    vm.openEdit({ id: 't1', name: '电工', hourly_rate: '50.00', description: '默认' })
    expect(vm.form.name).toBe('电工')
    expect(vm.form.hourly_rate).toBe('50.00')
    await vm.submitForm()
    expect(ut).toHaveBeenCalledWith('t1', expect.objectContaining({ name: '电工' }))
  })

  it('删除确认后调用 delete', async () => {
    const w = mountDialog()
    await flushPromises()
    const vm = w.vm as unknown as { handleDelete: (r: { id: string; name: string }) => Promise<void> }
    await vm.handleDelete({ id: 't1', name: '电工' })
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(dt).toHaveBeenCalledWith('t1')
  })

  it('无 manage 权限隐藏新增按钮', async () => {
    authState.can = false
    const w = mountDialog()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新增分类')).toBeFalsy()
  })
})
