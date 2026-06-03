import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { la, ca, ua, da } = vi.hoisted(() => ({
  la: vi.fn(),
  ca: vi.fn(),
  ua: vi.fn(),
  da: vi.fn(),
}))
vi.mock('@/api/assets', () => ({
  listAssets: la,
  createAsset: ca,
  updateAsset: ua,
  deleteAsset: da,
  listDowntimes: vi.fn().mockResolvedValue([]),
  addDowntime: vi.fn(),
  closeDowntime: vi.fn(),
}))
const { lac } = vi.hoisted(() => ({ lac: vi.fn() }))
vi.mock('@/api/assetCategories', () => ({
  listAssetCategories: lac,
  createAssetCategory: vi.fn(),
  updateAssetCategory: vi.fn(),
  deleteAssetCategory: vi.fn(),
}))
const { llm } = vi.hoisted(() => ({ llm: vi.fn() }))
vi.mock('@/api/locations', () => ({ listLocationsMini: llm }))
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/teams', () => ({ listTeams: vi.fn().mockResolvedValue([]) }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import AssetsView from '@/views/maindata/AssetsView.vue'

function mountView() {
  return mount(AssetsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  la.mockReset().mockResolvedValue([
    {
      id: 'a1',
      custom_id: 'A-001',
      name: '泵 1',
      description: '',
      parent_id: null,
      location_id: 'l1',
      category_id: 'c1',
      status: 'OPERATIONAL',
      serial_number: '',
      model: '',
      manufacturer: '',
      power: '',
      warranty_expiration_date: null,
      in_service_date: null,
      acquisition_cost: null,
      barcode: null,
      nfc_id: null,
      primary_user_id: null,
      assigned_user_ids: [],
      team_ids: [],
    },
    {
      id: 'a2',
      custom_id: 'A-002',
      name: '子泵',
      description: '',
      parent_id: 'a1',
      location_id: null,
      category_id: null,
      status: 'DOWN',
      serial_number: '',
      model: '',
      manufacturer: '',
      power: '',
      warranty_expiration_date: null,
      in_service_date: null,
      acquisition_cost: null,
      barcode: null,
      nfc_id: null,
      primary_user_id: null,
      assigned_user_ids: [],
      team_ids: [],
    },
  ])
  ca.mockReset().mockResolvedValue({})
  ua.mockReset().mockResolvedValue({})
  da.mockReset().mockResolvedValue(undefined)
  lac.mockReset().mockResolvedValue([{ id: 'c1', name: '泵类' }])
  llm.mockReset().mockResolvedValue([{ id: 'l1', name: '总部大楼', custom_id: 'L-001' }])
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('AssetsView', () => {
  it('加载并渲染资产树 + 状态/位置/分类映射', async () => {
    const w = mountView()
    await flushPromises()
    expect(la).toHaveBeenCalled()
    expect(w.text()).toContain('泵 1')
    expect(w.text()).toContain('子泵')
    expect(w.text()).toContain('总部大楼')
    expect(w.text()).toContain('泵类')
    expect(w.text()).toContain('运行中')
  })

  it('新建提交携带 name+status', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建资产')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '新设备'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ca).toHaveBeenCalled()
    expect(ca.mock.calls[0][0]).toMatchObject({ name: '新设备' })
    expect(ca.mock.calls[0][0]).toHaveProperty('status')
  })

  it('编辑根资产时父级选项排除自身与后代（防成环）', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    const a1 = vm.assets.find((x: any) => x.id === 'a1')
    expect(a1).toBeTruthy()
    vm.openEdit(a1)
    await nextTick()
    const optionIds = vm.parentOptions.map((a: any) => a.id)
    expect(optionIds).not.toContain('a1') // 自身
    expect(optionIds).not.toContain('a2') // 后代
  })

  it('点击行内「停机记录」接线 downtimeAsset/downtimeDialogVisible', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.downtimeDialogVisible).toBe(false)
    const dtBtn = w.findAll('.el-button').find((b) => b.text() === '停机记录')
    expect(dtBtn).toBeTruthy()
    await dtBtn!.trigger('click')
    await flushPromises()
    expect(vm.downtimeDialogVisible).toBe(true)
    expect(vm.downtimeAsset).toEqual({ id: 'a1', name: '泵 1' })
  })

  it('状态映射负向：DOWN → 停机 + danger tag', async () => {
    const w = mountView()
    await flushPromises()
    expect(w.text()).toContain('停机')
    const tags = w.findAll('.el-tag')
    const downTag = tags.find((t) => t.text() === '停机')
    const upTag = tags.find((t) => t.text() === '运行中')
    expect(downTag).toBeTruthy()
    expect(downTag!.classes()).toContain('el-tag--danger')
    expect(upTag).toBeTruthy()
    expect(upTag!.classes()).toContain('el-tag--success')
  })
})
