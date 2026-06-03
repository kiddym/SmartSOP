import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lr, cr, ur, dr, lp } = vi.hoisted(() => ({
  lr: vi.fn(),
  cr: vi.fn(),
  ur: vi.fn(),
  dr: vi.fn(),
  lp: vi.fn(),
}))
vi.mock('@/api/roles', () => ({
  listRoles: lr,
  createRole: cr,
  updateRole: ur,
  deleteRole: dr,
}))
vi.mock('@/api/permissions', () => ({ listPermissions: lp }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import RolesView from '@/views/platform/RolesView.vue'

function mountView() {
  return mount(RolesView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  lr.mockReset().mockResolvedValue([
    { id: 'r1', code: 'admin', name: '管理员', is_builtin: true, permissions: ['user.view'] },
    {
      id: 'r2',
      code: 'editor',
      name: '编辑员',
      is_builtin: false,
      permissions: ['user.view', 'user.create'],
    },
  ])
  cr.mockReset().mockResolvedValue({})
  ur.mockReset().mockResolvedValue({})
  dr.mockReset().mockResolvedValue(undefined)
  lp.mockReset().mockResolvedValue([
    {
      group: '平台',
      permissions: [
        { code: 'user.view', label: '用户-查看' },
        { code: 'user.create', label: '用户-创建' },
      ],
    },
  ])
})

describe('RolesView', () => {
  it('加载并渲染角色行，含类型与权限数列', async () => {
    const w = mountView()
    await flushPromises()
    expect(lr).toHaveBeenCalled()
    expect(lp).toHaveBeenCalled()
    expect(w.text()).toContain('管理员')
    expect(w.text()).toContain('编辑员')
    // 类型列
    expect(w.text()).toContain('内置')
    expect(w.text()).toContain('自定义')
    // 权限数列：精确定位到该行第 4 列（td index 3）
    // 列顺序：名称(0)/标识(1)/类型(2)/权限数(3)/操作(4)
    const rows = w.findAll('.el-table__body-wrapper tbody tr')
    const adminRow = rows.find((r) => r.text().includes('管理员'))!
    const editorRow = rows.find((r) => r.text().includes('编辑员'))!
    expect(adminRow.findAll('td').at(3)!.text()).toBe('1')
    expect(editorRow.findAll('td').at(3)!.text()).toBe('2')
  })

  it('内置角色行的编辑/删除按钮被禁用', async () => {
    const w = mountView()
    await flushPromises()
    // 找到内置角色「管理员」所在行
    const rows = w.findAll('.el-table__body-wrapper tbody tr')
    const builtinRow = rows.find((r) => r.text().includes('管理员'))
    expect(builtinRow).toBeTruthy()
    const builtinBtns = builtinRow!.findAll('.el-button')
    // 至少一个操作按钮且全部禁用
    expect(builtinBtns.length).toBeGreaterThan(0)
    for (const b of builtinBtns) {
      expect(b.classes()).toContain('is-disabled')
    }

    // 自定义角色「编辑员」按钮不应禁用
    const customRow = rows.find((r) => r.text().includes('编辑员'))
    expect(customRow).toBeTruthy()
    const customBtns = customRow!.findAll('.el-button')
    expect(customBtns.length).toBeGreaterThan(0)
    for (const b of customBtns) {
      expect(b.classes()).not.toContain('is-disabled')
    }
  })

  it('新建提交携带选中的 permissions', async () => {
    const w = mountView()
    await flushPromises()

    // 打开新建对话框
    const newBtn = w.findAll('.el-button').find((b) => b.text() === '新建角色')
    expect(newBtn).toBeTruthy()
    await newBtn!.trigger('click')
    await flushPromises()

    // 填 code / name
    const codeInput = document.querySelector(
      '.el-dialog input[placeholder="请输入角色标识"]',
    ) as HTMLInputElement
    expect(codeInput).toBeTruthy()
    codeInput.value = 'viewer'
    codeInput.dispatchEvent(new Event('input'))

    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入角色名称"]',
    ) as HTMLInputElement
    expect(nameInput).toBeTruthy()
    nameInput.value = '查看员'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()

    // 勾选权限：通过 label 文本匹配 checkbox
    const checkboxes = Array.from(document.querySelectorAll('.el-dialog .el-checkbox'))
    const target = checkboxes.find((c) => c.textContent?.includes('用户-查看')) as HTMLElement
    expect(target).toBeTruthy()
    ;(target.querySelector('input') as HTMLInputElement)?.click()
    await flushPromises()

    // 提交
    const submitBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    expect(submitBtn).toBeTruthy()
    submitBtn.click()
    await flushPromises()

    expect(cr).toHaveBeenCalled()
    const arg = cr.mock.calls[0][0]
    expect(arg).toMatchObject({ code: 'viewer', name: '查看员' })
    expect(arg.permissions).toContain('user.view')
  })
})
