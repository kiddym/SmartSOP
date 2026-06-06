import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lp, gp, cp, up, dp, ep, dsp, gen, la, addc } = vi.hoisted(() => ({
  lp: vi.fn(),
  gp: vi.fn(),
  cp: vi.fn(),
  up: vi.fn(),
  dp: vi.fn(),
  ep: vi.fn(),
  dsp: vi.fn(),
  gen: vi.fn(),
  la: vi.fn(),
  addc: vi.fn(),
}))
vi.mock('@/api/preventiveMaintenances', () => ({
  listPMs: lp,
  getPM: gp,
  createPM: cp,
  updatePM: up,
  deletePM: dp,
  enablePM: ep,
  disablePM: dsp,
  generatePM: gen,
  listPMActivities: la,
  addPMComment: addc,
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
vi.mock('@/api/procedures', () => ({
  listProceduresMini: vi.fn().mockResolvedValue([{ id: 'pr1', name: '保养SOP' }]),
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import PreventiveMaintenancesView from '@/views/maintenance/PreventiveMaintenancesView.vue'

function mountView() {
  return mount(PreventiveMaintenancesView, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

const pm1 = {
  id: 'p1',
  custom_id: 'PM-001',
  title: '月度保养',
  description: '',
  priority: 'MEDIUM',
  asset_id: 'a1',
  location_id: 'l1',
  primary_user_id: 'u1',
  procedure_id: null,
  start_date: '2026-06-01',
  frequency_unit: 'MONTH',
  frequency_value: 1,
  due_date_delay: 3,
  ends_on: '2026-12-31',
  next_due_date: '2026-07-01',
  is_enabled: true,
  last_generated_at: null,
  last_work_order_id: 'wo1',
  assignee_ids: [],
  team_ids: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lp.mockReset().mockResolvedValue([pm1])
  gp.mockReset().mockResolvedValue(pm1)
  cp.mockReset().mockResolvedValue({})
  up.mockReset().mockResolvedValue({})
  dp.mockReset().mockResolvedValue(undefined)
  ep.mockReset().mockResolvedValue({})
  dsp.mockReset().mockResolvedValue({})
  gen.mockReset().mockResolvedValue({})
  la.mockReset().mockResolvedValue([])
  addc.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PreventiveMaintenancesView', () => {
  it('加载并渲染 PM + 频率中文 + 下次到期 + 已生成工单徽标', async () => {
    const w = mountView()
    await flushPromises()
    expect(lp).toHaveBeenCalled()
    expect(w.text()).toContain('PM-001')
    expect(w.text()).toContain('月度保养')
    expect(w.text()).toContain('每 1 月')
    expect(w.text()).toContain('2026-07-01')
    expect(w.text()).toContain('已生成工单')
  })

  it('新建提交携带 title + 排程字段', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建预防性维护')
    await addBtn!.trigger('click')
    await flushPromises()
    const vm = w.vm as any
    vm.form.title = '周度点检'
    vm.form.start_date = '2026-06-10'
    vm.form.frequency_unit = 'WEEK'
    vm.form.frequency_value = 2
    vm.form.due_date_delay = 7
    vm.form.ends_on = '2027-01-01'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cp).toHaveBeenCalled()
    expect(cp.mock.calls[0][0]).toMatchObject({
      title: '周度点检',
      start_date: '2026-06-10',
      frequency_unit: 'WEEK',
      frequency_value: 2,
      due_date_delay: 7,
      ends_on: '2027-01-01',
    })
  })

  it('编辑回填排程字段 due_date_delay/ends_on', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    vm.openEdit(pm1)
    await flushPromises()
    expect(vm.form.due_date_delay).toBe(3)
    expect(vm.form.ends_on).toBe('2026-12-31')
    vm.form.due_date_delay = 0
    vm.form.ends_on = null
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(up).toHaveBeenCalled()
    expect(up.mock.calls[0][1]).toMatchObject({ due_date_delay: 0, ends_on: null })
  })

  it('手动生成经确认调 generatePM', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.handleGenerate(pm1)
    await flushPromises()
    expect(gen).toHaveBeenCalledWith('p1')
  })

  it('停用调 disablePM（当前启用，toggle 不弹确认）', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.toggleEnabled(pm1)
    await flushPromises()
    expect(dsp).toHaveBeenCalledWith('p1')
  })

  it('无权限隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建预防性维护')).toBeFalsy()
  })
})
