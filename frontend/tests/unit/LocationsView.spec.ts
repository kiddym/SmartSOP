import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ll, cl, ul, dl, lu, lt } = vi.hoisted(() => ({
  ll: vi.fn(),
  cl: vi.fn(),
  ul: vi.fn(),
  dl: vi.fn(),
  lu: vi.fn(),
  lt: vi.fn(),
}))
vi.mock('@/api/locations', () => ({
  listLocations: ll,
  createLocation: cl,
  updateLocation: ul,
  deleteLocation: dl,
}))
vi.mock('@/api/users', () => ({ listUsers: lu }))
vi.mock('@/api/teams', () => ({ listTeams: lt }))
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
      assigned_user_ids: [],
      team_ids: [],
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
      assigned_user_ids: [],
      team_ids: [],
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
