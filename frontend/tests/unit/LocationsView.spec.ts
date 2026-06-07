import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ll, cl, ul, dl, lu, lt, lv, lc } = vi.hoisted(() => ({
  ll: vi.fn(),
  cl: vi.fn(),
  ul: vi.fn(),
  dl: vi.fn(),
  lu: vi.fn(),
  lt: vi.fn(),
  lv: vi.fn(),
  lc: vi.fn(),
}))
vi.mock('@/api/locations', () => ({
  listLocations: ll,
  createLocation: cl,
  updateLocation: ul,
  deleteLocation: dl,
}))
vi.mock('@/api/users', () => ({ listUsers: lu }))
vi.mock('@/api/teams', () => ({ listTeams: lt }))
vi.mock('@/api/vendors', () => ({ listVendorsMini: lv }))
vi.mock('@/api/customers', () => ({ listCustomersMini: lc }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import LocationsView from '@/views/maindata/LocationsView.vue'

function mountView() {
  return mount(LocationsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  ll.mockReset().mockResolvedValue([
    {
      id: 'l1',
      custom_id: 'L-001',
      name: '总部大楼',
      description: '',
      parent_id: null,
      address: '北京',
      longitude: null,
      latitude: null,
      image_url: null,
      assigned_user_ids: [],
      team_ids: [],
      vendor_ids: [],
      customer_ids: [],
      custom_values: {},
    },
    {
      id: 'l2',
      custom_id: 'L-002',
      name: '3 楼',
      description: '',
      parent_id: 'l1',
      address: '',
      longitude: null,
      latitude: null,
      image_url: null,
      assigned_user_ids: [],
      team_ids: [],
      vendor_ids: [],
      customer_ids: [],
      custom_values: {},
    },
  ])
  cl.mockReset().mockResolvedValue({})
  ul.mockReset().mockResolvedValue({})
  dl.mockReset().mockResolvedValue(undefined)
  lu.mockReset().mockResolvedValue([
    {
      id: 'u1',
      name: '张三',
      email: 'a@b.com',
      status: 'active',
      role_id: null,
      locale: 'zh',
      last_login_at: null,
      created_at: '2026-01-01T00:00:00Z',
    },
  ])
  lt.mockReset().mockResolvedValue([{ id: 't1', name: '机械组', description: '', member_ids: [] }])
  lv.mockReset().mockResolvedValue([{ id: 'v1', name: '供应商甲', custom_id: 'V-001' }])
  lc.mockReset().mockResolvedValue([{ id: 'c1', name: '客户乙', custom_id: 'C-001' }])
})

// el-dialog 通过 teleport 挂到 document.body，attachTo 不会随组件卸载清理，
// 测试间会残留旧 dialog 干扰 querySelector，这里手动清空。
afterEach(() => {
  document.body.innerHTML = ''
})

describe('LocationsView', () => {
  it('加载并渲染位置树行（含父子）', async () => {
    const w = mountView()
    await flushPromises()
    expect(ll).toHaveBeenCalled()
    expect(w.text()).toContain('总部大楼')
    expect(w.text()).toContain('3 楼')
    expect(w.text()).toContain('L-001')
  })

  it('新建提交携带 name', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建位置')
    expect(addBtn).toBeTruthy()
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '新机房'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const submitBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    submitBtn.click()
    await flushPromises()
    expect(cl).toHaveBeenCalled()
    expect(cl.mock.calls[0][0]).toMatchObject({ name: '新机房' })
  })

  it('新建提交携带主图与供应商/客户关联', async () => {
    const w = mountView()
    await flushPromises()
    expect(lv).toHaveBeenCalled()
    expect(lc).toHaveBeenCalled()
    const vm = w.vm as unknown as {
      openCreate: () => void
      form: {
        name: string
        image_url: string
        vendor_ids: string[]
        customer_ids: string[]
      }
      submitForm: () => Promise<void>
    }
    vm.openCreate()
    vm.form.name = '新机房'
    vm.form.image_url = '/img/loc.png'
    vm.form.vendor_ids = ['v1']
    vm.form.customer_ids = ['c1']
    await vm.submitForm()
    await flushPromises()
    expect(cl).toHaveBeenCalled()
    expect(cl.mock.calls[0][0]).toMatchObject({
      name: '新机房',
      image_url: '/img/loc.png',
      vendor_ids: ['v1'],
      customer_ids: ['c1'],
    })
  })

  it('编辑回填名称到表单', async () => {
    const w = mountView()
    await flushPromises()
    const editBtn = w.findAll('.el-button').find((b) => b.text() === '编辑')
    expect(editBtn).toBeTruthy()
    await editBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    expect(nameInput.value).toBe('总部大楼')
  })

  it('编辑时父位置选项排除自身与后代（防环）', async () => {
    const w = mountView()
    await flushPromises()
    // 第一个「编辑」按钮对应根行 l1（default-expand-all），其后代为 l2。
    const editBtn = w.findAll('.el-button').find((b) => b.text() === '编辑')
    await editBtn!.trigger('click')
    await flushPromises()
    const vm = w.vm as unknown as { parentOptions: Array<{ id: string }> }
    const ids = vm.parentOptions.map((l) => l.id)
    expect(ids).not.toContain('l1')
    expect(ids).not.toContain('l2')
  })

  it('删除经确认调用 deleteLocation', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await flushPromises()
    expect(dl).toHaveBeenCalled()
  })
})
