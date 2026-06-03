import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lt, ct, ut, dt, sm, lu } = vi.hoisted(() => ({
  lt: vi.fn(),
  ct: vi.fn(),
  ut: vi.fn(),
  dt: vi.fn(),
  sm: vi.fn(),
  lu: vi.fn(),
}))
vi.mock('@/api/teams', () => ({
  listTeams: lt,
  createTeam: ct,
  updateTeam: ut,
  deleteTeam: dt,
  setTeamMembers: sm,
}))
vi.mock('@/api/users', () => ({ listUsers: lu }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import TeamsView from '@/views/platform/TeamsView.vue'

function mountView() {
  return mount(TeamsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  lt.mockReset().mockResolvedValue([
    { id: 't1', name: '运维班', description: '夜班维护', member_ids: ['u1'] },
    { id: 't2', name: '电气组', description: '电气专项', member_ids: ['u1', 'u2'] },
  ])
  ct.mockReset().mockResolvedValue({})
  ut.mockReset().mockResolvedValue({})
  dt.mockReset().mockResolvedValue(undefined)
  sm.mockReset().mockResolvedValue({})
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
    {
      id: 'u2',
      name: '李四',
      email: 'c@d.com',
      status: 'active',
      role_id: null,
      locale: 'zh',
      last_login_at: null,
      created_at: '2026-01-01T00:00:00Z',
    },
  ])
})

describe('TeamsView', () => {
  it('加载并渲染团队行，含名称/描述/成员数列', async () => {
    const w = mountView()
    await flushPromises()
    expect(lt).toHaveBeenCalled()
    expect(lu).toHaveBeenCalled()
    expect(w.text()).toContain('运维班')
    expect(w.text()).toContain('电气组')
    expect(w.text()).toContain('夜班维护')
    // 列顺序：名称(0)/描述(1)/成员数(2)/操作(3)
    const rows = w.findAll('.el-table__body-wrapper tbody tr')
    const r1 = rows.find((r) => r.text().includes('运维班'))!
    const r2 = rows.find((r) => r.text().includes('电气组'))!
    expect(r1.findAll('td').at(2)!.text()).toBe('1')
    expect(r2.findAll('td').at(2)!.text()).toBe('2')
  })

  it('成员管理提交以 (teamId, user_ids) 调用 setTeamMembers', async () => {
    const w = mountView()
    await flushPromises()

    // 打开 t1 行的成员管理对话框
    const rows = w.findAll('.el-table__body-wrapper tbody tr')
    const r1 = rows.find((r) => r.text().includes('运维班'))!
    const memberBtn = r1.findAll('.el-button').find((b) => b.text() === '成员')
    expect(memberBtn).toBeTruthy()
    await memberBtn!.trigger('click')
    await flushPromises()

    // 定位成员管理对话框（含成员选择框）
    const memberSelect = document.querySelector('.el-dialog .el-select') as HTMLElement
    expect(memberSelect).toBeTruthy()
    const memberDialog = memberSelect.closest('.el-dialog') as HTMLElement

    // 打开下拉
    ;(memberSelect.querySelector('.el-select__wrapper') as HTMLElement)?.click()
    await flushPromises()

    // 选择李四（u2）：通过 select 下拉项文本匹配
    const options = Array.from(document.querySelectorAll('.el-select-dropdown__item'))
    const liSi = options.find((o) => o.textContent?.includes('李四')) as HTMLElement
    expect(liSi).toBeTruthy()
    liSi.click()
    await flushPromises()

    // 提交
    const submitBtn = Array.from(memberDialog.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    expect(submitBtn).toBeTruthy()
    submitBtn.click()
    await flushPromises()

    expect(sm).toHaveBeenCalled()
    const [tid, ids] = sm.mock.calls[0]
    expect(tid).toBe('t1')
    expect(ids).toContain('u1') // 预填的原有成员
    expect(ids).toContain('u2') // 新选中
  })

  it('新建提交携带 name/description', async () => {
    const w = mountView()
    await flushPromises()

    const newBtn = w.findAll('.el-button').find((b) => b.text() === '新建团队')
    expect(newBtn).toBeTruthy()
    await newBtn!.trigger('click')
    await flushPromises()

    // 定位到含「请输入团队名称」输入框的对话框（新建/编辑对话框）
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入团队名称"]',
    ) as HTMLInputElement
    expect(nameInput).toBeTruthy()
    const createDialog = nameInput.closest('.el-dialog') as HTMLElement
    expect(createDialog).toBeTruthy()
    nameInput.value = '机械组'
    nameInput.dispatchEvent(new Event('input'))

    const descInput = createDialog.querySelector(
      'textarea[placeholder="请输入描述"]',
    ) as HTMLTextAreaElement
    expect(descInput).toBeTruthy()
    descInput.value = '机械专项'
    descInput.dispatchEvent(new Event('input'))
    await flushPromises()

    const submitBtn = Array.from(createDialog.querySelectorAll('.el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    expect(submitBtn).toBeTruthy()
    submitBtn.click()
    await flushPromises()

    expect(ct).toHaveBeenCalled()
    expect(ct.mock.calls[0][0]).toMatchObject({ name: '机械组', description: '机械专项' })
  })
})
