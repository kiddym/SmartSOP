import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lp, cp, up, dp } = vi.hoisted(() => ({
  lp: vi.fn(),
  cp: vi.fn(),
  up: vi.fn(),
  dp: vi.fn(),
}))
vi.mock('@/api/parts', () => ({
  listParts: lp,
  listPartsMini: vi.fn().mockResolvedValue([]),
  createPart: cp,
  updatePart: up,
  deletePart: dp,
}))
const { lpc } = vi.hoisted(() => ({ lpc: vi.fn() }))
vi.mock('@/api/partCategories', () => ({
  listPartCategories: lpc,
  createPartCategory: vi.fn(),
  updatePartCategory: vi.fn(),
  deletePartCategory: vi.fn(),
}))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import PartsView from '@/views/inventory/PartsView.vue'

function mountView() {
  return mount(PartsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lp.mockReset().mockResolvedValue([
    {
      id: 'p1',
      custom_id: 'P-001',
      name: '深沟球轴承',
      description: '',
      cost: '12.5',
      quantity: '3',
      min_quantity: '5',
      unit: '个',
      barcode: null,
      non_stock: false,
      is_low_stock: true,
      category_id: 'c1',
      assignee_ids: [],
      team_ids: [],
      asset_ids: [],
      location_ids: [],
      pm_ids: [],
    },
  ])
  cp.mockReset().mockResolvedValue({})
  up.mockReset().mockResolvedValue({})
  dp.mockReset().mockResolvedValue(undefined)
  lpc.mockReset().mockResolvedValue([{ id: 'c1', name: '轴承', description: '' }])
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PartsView', () => {
  it('加载并渲染备件 + 分类映射 + 低库存标记', async () => {
    const w = mountView()
    await flushPromises()
    expect(lp).toHaveBeenCalled()
    expect(w.text()).toContain('深沟球轴承')
    expect(w.text()).toContain('P-001')
    expect(w.text()).toContain('轴承') // category_id→name
    expect(w.text()).toContain('低库存') // is_low_stock tag
  })

  it('新建提交携带 name', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建备件')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '新备件'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cp).toHaveBeenCalled()
    expect(cp.mock.calls[0][0]).toMatchObject({ name: '新备件' })
  })

  it('低库存过滤开关触发带参重拉', async () => {
    const w = mountView()
    await flushPromises()
    lp.mockClear()
    // 找到低库存过滤开关（el-switch / el-checkbox），切换后应以 { low_stock: true } 重拉
    const sw = w.find('.el-switch')
    expect(sw.exists()).toBe(true)
    await sw.trigger('click')
    await flushPromises()
    expect(lp).toHaveBeenCalledWith({ low_stock: true })
  })

  it('无权限隐藏新建备件按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建备件')).toBeFalsy()
  })
})
