import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lr, gr, cr, ur, dr, ar, rr, cnr, la, addc } = vi.hoisted(() => ({
  lr: vi.fn(),
  gr: vi.fn(),
  cr: vi.fn(),
  ur: vi.fn(),
  dr: vi.fn(),
  ar: vi.fn(),
  rr: vi.fn(),
  cnr: vi.fn(),
  la: vi.fn(),
  addc: vi.fn(),
}))
vi.mock('@/api/requests', () => ({
  listRequests: lr,
  getRequest: gr,
  createRequest: cr,
  updateRequest: ur,
  deleteRequest: dr,
  approveRequest: ar,
  rejectRequest: rr,
  cancelRequest: cnr,
  listRequestActivities: la,
  addRequestComment: addc,
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

import RequestsView from '@/views/maintenance/RequestsView.vue'

function mountView() {
  return mount(RequestsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const pendingReq = {
  id: 'r1',
  custom_id: 'RQ-001',
  title: '泵漏油',
  description: '',
  priority: 'HIGH',
  due_date: null,
  asset_id: 'a1',
  location_id: 'l1',
  status: 'PENDING',
  work_order_id: null,
  resolution_note: '',
  resolved_by_user_id: null,
  resolved_at: null,
}
const approvedReq = {
  ...pendingReq,
  id: 'r2',
  custom_id: 'RQ-002',
  status: 'APPROVED',
  work_order_id: 'wo1',
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lr.mockReset().mockResolvedValue([pendingReq, approvedReq])
  gr.mockReset().mockResolvedValue(pendingReq)
  cr.mockReset().mockResolvedValue({})
  ur.mockReset().mockResolvedValue({})
  dr.mockReset().mockResolvedValue(undefined)
  ar.mockReset().mockResolvedValue({})
  rr.mockReset().mockResolvedValue({})
  cnr.mockReset().mockResolvedValue({})
  la.mockReset().mockResolvedValue([
    {
      id: 'ac1',
      activity_type: 'COMMENT',
      actor_user_id: 'u1',
      from_status: null,
      to_status: null,
      comment: '已查看',
      created_at: '2026-06-01T01:00:00',
    },
  ])
  addc.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('RequestsView', () => {
  it('加载并渲染请求 + 状态中文 + 资产名 + 已生成工单徽标', async () => {
    const w = mountView()
    await flushPromises()
    expect(lr).toHaveBeenCalled()
    expect(w.text()).toContain('RQ-001')
    expect(w.text()).toContain('泵漏油')
    expect(w.text()).toContain('待审批')
    expect(w.text()).toContain('已批准')
    expect(w.text()).toContain('泵')
    expect(w.text()).toContain('已生成工单')
  })

  it('新建提交携带 title', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建请求')
    await addBtn!.trigger('click')
    await flushPromises()
    const titleInput = document.querySelector(
      '.el-dialog input[placeholder="请输入标题"]',
    ) as HTMLInputElement
    titleInput.value = '电机异响'
    titleInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cr).toHaveBeenCalled()
    expect(cr.mock.calls[0][0]).toMatchObject({ title: '电机异响' })
  })

  it('审批指派对话框提交调 approveRequest 带指派', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    vm.openApprove(pendingReq)
    await flushPromises()
    vm.approveForm.primary_user_id = 'u1'
    vm.approveForm.assignee_ids = ['u1']
    vm.approveForm.team_ids = ['t1']
    await flushPromises()
    const confirmBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '批准并生成工单',
    ) as HTMLElement
    confirmBtn.click()
    await flushPromises()
    expect(ar).toHaveBeenCalled()
    expect(ar.mock.calls[0][0]).toBe('r1')
    expect(ar.mock.calls[0][1]).toMatchObject({
      primary_user_id: 'u1',
      assignee_ids: ['u1'],
      team_ids: ['t1'],
    })
  })

  it('驳回经 prompt 调 rejectRequest 带 reason', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: '信息不足' } as never)
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.handleReject(pendingReq)
    await flushPromises()
    expect(rr).toHaveBeenCalledWith('r1', { reason: '信息不足' })
  })

  it('无权限隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建请求')).toBeFalsy()
  })
})
