import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lm, gm, cm, um, dm, lrd, sr, lt, et, dt2 } = vi.hoisted(() => ({
  lm: vi.fn(),
  gm: vi.fn(),
  cm: vi.fn(),
  um: vi.fn(),
  dm: vi.fn(),
  lrd: vi.fn(),
  sr: vi.fn(),
  lt: vi.fn(),
  et: vi.fn(),
  dt2: vi.fn(),
}))
vi.mock('@/api/meters', () => ({
  listMeters: lm,
  getMeter: gm,
  createMeter: cm,
  updateMeter: um,
  deleteMeter: dm,
  listReadings: lrd,
  submitReading: sr,
  listTriggers: lt,
  createTrigger: vi.fn(),
  updateTrigger: vi.fn(),
  deleteTrigger: vi.fn(),
  enableTrigger: et,
  disableTrigger: dt2,
}))
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
vi.mock('@/api/procedures', () => ({ listProceduresMini: vi.fn().mockResolvedValue([]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import MetersView from '@/views/maintenance/MetersView.vue'

function mountView() {
  return mount(MetersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const meter1 = {
  id: 'm1',
  custom_id: 'MTR-001',
  name: '油位计',
  unit: '小时',
  update_frequency_days: 30,
  asset_id: 'a1',
  location_id: 'l1',
}
const reading1 = {
  id: 'rd1',
  meter_id: 'm1',
  value: '120.0000',
  reading_at: '2026-06-02T00:00:00',
  recorded_by_user_id: 'u1',
}
const trigger1 = {
  id: 'tg1',
  meter_id: 'm1',
  name: '高位',
  comparator: 'MORE_THAN',
  threshold: '100',
  is_armed: true,
  is_enabled: true,
  priority: 'HIGH',
  title: '排油',
  description: '',
  primary_user_id: null,
  procedure_id: null,
  last_triggered_at: null,
  last_work_order_id: null,
  assignee_ids: [],
  team_ids: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lm.mockReset().mockResolvedValue([meter1])
  gm.mockReset().mockResolvedValue(meter1)
  cm.mockReset().mockResolvedValue({})
  um.mockReset().mockResolvedValue({})
  dm.mockReset().mockResolvedValue(undefined)
  lrd.mockReset().mockResolvedValue([reading1])
  sr.mockReset().mockResolvedValue({ reading: reading1, generated_work_order_ids: ['wo9'] })
  lt.mockReset().mockResolvedValue([trigger1])
  et.mockReset().mockResolvedValue({})
  dt2.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MetersView', () => {
  it('加载并渲染计量行 + 名称/单位/资产名', async () => {
    const w = mountView()
    await flushPromises()
    expect(lm).toHaveBeenCalled()
    expect(w.text()).toContain('MTR-001')
    expect(w.text()).toContain('油位计')
    expect(w.text()).toContain('小时')
    expect(w.text()).toContain('泵')
  })

  it('新建提交携带 name', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建计量')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '温度计'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cm).toHaveBeenCalled()
    expect(cm.mock.calls[0][0]).toMatchObject({ name: '温度计' })
  })

  it('打开详情拉读数与触发器', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openDetail(meter1)
    await flushPromises()
    expect(gm).toHaveBeenCalledWith('m1')
    expect(lrd).toHaveBeenCalledWith('m1')
    expect(lt).toHaveBeenCalledWith('m1')
    expect(document.body.textContent).toContain('120')
    expect(document.body.textContent).toContain('高位')
  })

  it('提交读数调 submitReading 并提示触发工单', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openDetail(meter1)
    await flushPromises()
    vm.readingValue = '150'
    await vm.handleSubmitReading()
    await flushPromises()
    expect(sr).toHaveBeenCalled()
    expect(sr.mock.calls[0][0]).toBe('m1')
    expect(sr.mock.calls[0][1]).toMatchObject({ value: '150' })
  })

  it('读数未触发工单：仍提交并刷新读数与触发器', async () => {
    sr.mockResolvedValue({ reading: reading1, generated_work_order_ids: [] })
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openDetail(meter1)
    await flushPromises()
    lrd.mockClear()
    lt.mockClear()
    vm.readingValue = '90'
    await vm.handleSubmitReading()
    await flushPromises()
    expect(sr).toHaveBeenCalled()
    expect(sr.mock.calls[0][1]).toMatchObject({ value: '90' })
    // 提交后应重新拉取读数与触发器（is_armed 边沿可能变化）
    expect(lrd).toHaveBeenCalledWith('m1')
    expect(lt).toHaveBeenCalledWith('m1')
  })

  it('无权限隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建计量')).toBeFalsy()
  })
})
