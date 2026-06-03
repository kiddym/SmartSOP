import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lu, cu, iu, uu, du, lr } = vi.hoisted(() => ({
  lu: vi.fn(),
  cu: vi.fn(),
  iu: vi.fn(),
  uu: vi.fn(),
  du: vi.fn(),
  lr: vi.fn(),
}))
vi.mock('@/api/users', () => ({
  listUsers: lu,
  createUser: cu,
  inviteUser: iu,
  updateUser: uu,
  deleteUser: du,
}))
vi.mock('@/api/roles', () => ({ listRoles: lr }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import UsersView from '@/views/platform/UsersView.vue'
import { ElMessageBox } from 'element-plus'

function mountView() {
  return mount(UsersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  lu.mockReset().mockResolvedValue([
    {
      id: 'u1',
      email: 'a@b.com',
      name: '张三',
      status: 'active',
      role_id: 'r1',
      locale: 'zh',
      last_login_at: null,
      created_at: '2026-06-01T00:00:00Z',
    },
  ])
  cu.mockReset().mockResolvedValue({})
  iu.mockReset().mockResolvedValue({ id: 'x', email: 'new@b.com', status: 'invited' })
  uu.mockReset().mockResolvedValue({})
  du.mockReset().mockResolvedValue(undefined)
  lr.mockReset().mockResolvedValue([
    { id: 'r1', code: 'admin', name: '管理员', is_builtin: true, permissions: [] },
  ])
})

describe('UsersView', () => {
  it('加载并渲染用户行，role_id 映射为角色名', async () => {
    const w = mountView()
    await flushPromises()
    expect(lu).toHaveBeenCalled()
    expect(lr).toHaveBeenCalled()
    expect(w.text()).toContain('张三')
    expect(w.text()).toContain('a@b.com')
    expect(w.text()).toContain('管理员')
  })

  it('邀请用户提交仅传 email/role_id，不含 name、password', async () => {
    iu.mockResolvedValue({ id: 'i1', email: 'new@x.com', status: 'invited' })
    const w = mountView()
    await flushPromises()

    // open the invite dialog via toolbar button
    const inviteBtn = w.findAll('.el-button').find((b) => b.text() === '邀请用户')
    expect(inviteBtn).toBeTruthy()
    await inviteBtn!.trigger('click')
    await flushPromises()

    // fill email (+ optional role) directly through the dialog's email input
    const emailInput = document.querySelector(
      '.el-dialog input[placeholder="请输入邮箱"]',
    ) as HTMLInputElement
    expect(emailInput).toBeTruthy()
    emailInput.value = 'new@x.com'
    emailInput.dispatchEvent(new Event('input'))
    await flushPromises()

    // submit via dialog footer "发送邀请" button
    const submitBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '发送邀请',
    ) as HTMLElement
    expect(submitBtn).toBeTruthy()
    submitBtn.click()
    await flushPromises()

    expect(iu).toHaveBeenCalledWith(expect.objectContaining({ email: 'new@x.com' }))
    const arg = iu.mock.calls[0][0]
    expect(arg).not.toHaveProperty('name')
    expect(arg).not.toHaveProperty('password')
  })

  it('确认删除后调用 deleteUser', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    expect(delBtn).toBeTruthy()
    await delBtn!.trigger('click')
    await flushPromises()
    expect(du).toHaveBeenCalledWith('u1')
  })
})
