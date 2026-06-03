import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lpo, gpo, cpo, upo, dpo, sub, app, rej, can, acts } = vi.hoisted(() => ({
  lpo: vi.fn(),
  gpo: vi.fn(),
  cpo: vi.fn(),
  upo: vi.fn(),
  dpo: vi.fn(),
  sub: vi.fn(),
  app: vi.fn(),
  rej: vi.fn(),
  can: vi.fn(),
  acts: vi.fn(),
}))
vi.mock('@/api/purchaseOrders', () => ({
  listPurchaseOrders: lpo,
  getPurchaseOrder: gpo,
  createPurchaseOrder: cpo,
  updatePurchaseOrder: upo,
  deletePurchaseOrder: dpo,
  submitPurchaseOrder: sub,
  approvePurchaseOrder: app,
  rejectPurchaseOrder: rej,
  cancelPurchaseOrder: can,
  listPurchaseOrderActivities: acts,
}))
vi.mock('@/api/vendors', () => ({
  listVendorsMini: vi.fn().mockResolvedValue([{ id: 'v1', name: '一号供应商' }]),
}))
vi.mock('@/api/parts', () => ({
  listPartsMini: vi.fn().mockResolvedValue([{ id: 'p1', name: '轴承', custom_id: 'P-001' }]),
}))
vi.mock('@/api/purchaseOrderCategories', () => ({
  listPurchaseOrderCategories: vi.fn().mockResolvedValue([]),
  createPurchaseOrderCategory: vi.fn(),
  updatePurchaseOrderCategory: vi.fn(),
  deletePurchaseOrderCategory: vi.fn(),
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import PurchaseOrdersView from '@/views/inventory/PurchaseOrdersView.vue'

function mountView() {
  return mount(PurchaseOrdersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const draftPO = {
  id: 'po1',
  custom_id: 'PO-001',
  vendor_id: 'v1',
  status: 'DRAFT',
  notes: '',
  category_id: null,
  shipping_address: '',
  shipping_method: '',
  terms_of_payment: '',
  expected_delivery_date: null,
  resolution_note: '',
  resolved_by_user_id: null,
  resolved_at: null,
  lines: [{ id: 'l1', part_id: 'p1', quantity: '10', unit_cost: '5', line_total: '50' }],
  total_cost: '50',
}
const submittedPO = { ...draftPO, id: 'po2', custom_id: 'PO-002', status: 'SUBMITTED' }

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lpo.mockReset().mockResolvedValue([draftPO, submittedPO])
  gpo
    .mockReset()
    .mockImplementation((id: string) => Promise.resolve(id === 'po2' ? submittedPO : draftPO))
  cpo.mockReset().mockResolvedValue({})
  upo.mockReset().mockResolvedValue({})
  dpo.mockReset().mockResolvedValue(undefined)
  sub.mockReset().mockResolvedValue({})
  app.mockReset().mockResolvedValue({})
  rej.mockReset().mockResolvedValue({})
  can.mockReset().mockResolvedValue({})
  acts.mockReset().mockResolvedValue([
    {
      id: 'a1',
      activity_type: 'STATUS_CHANGE',
      actor_user_id: null,
      from_status: 'DRAFT',
      to_status: 'SUBMITTED',
      comment: '',
      created_at: '2026-06-01T00:00:00',
    },
  ])
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PurchaseOrdersView', () => {
  it('加载并渲染采购单 + 供应商名 + 状态中文 + 总额', async () => {
    const w = mountView()
    await flushPromises()
    expect(lpo).toHaveBeenCalled()
    expect(w.text()).toContain('PO-001')
    expect(w.text()).toContain('一号供应商') // vendor_id→name
    expect(w.text()).toContain('草稿') // DRAFT→中文
    expect(w.text()).toContain('已提交') // SUBMITTED→中文
  })

  it('新建提交携带 vendor_id + lines', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建采购单')
    await addBtn!.trigger('click')
    await flushPromises()
    // 选供应商
    const vm = w.vm as any
    vm.form.vendor_id = 'v1'
    // 添加一明细行
    vm.addLine()
    vm.form.lines[0].part_id = 'p1'
    vm.form.lines[0].quantity = '2'
    vm.form.lines[0].unit_cost = '3'
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cpo).toHaveBeenCalled()
    expect(cpo.mock.calls[0][0]).toMatchObject({
      vendor_id: 'v1',
      lines: [{ part_id: 'p1', quantity: '2', unit_cost: '3' }],
    })
  })

  it('打开 DRAFT 采购单显示提交按钮并调 submit', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openEdit(draftPO)
    await flushPromises()
    expect(gpo).toHaveBeenCalledWith('po1')
    const submitBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '提交',
    ) as HTMLElement
    expect(submitBtn).toBeTruthy()
    submitBtn.click()
    await flushPromises()
    expect(sub).toHaveBeenCalledWith('po1')
  })

  it('打开 SUBMITTED 采购单显示批准/驳回并调 approve', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openEdit(submittedPO)
    await flushPromises()
    const approveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '批准',
    ) as HTMLElement
    expect(approveBtn).toBeTruthy()
    approveBtn.click()
    await flushPromises()
    expect(app).toHaveBeenCalled()
    expect(app.mock.calls[0][0]).toBe('po2')
  })

  it('打开 APPROVED 采购单为只读：隐藏保存与添加明细行', async () => {
    const approvedPO = { ...draftPO, id: 'po3', custom_id: 'PO-003', status: 'APPROVED' }
    gpo.mockImplementation(() => Promise.resolve(approvedPO))
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    await vm.openEdit(approvedPO)
    await flushPromises()
    const btns = Array.from(document.querySelectorAll('.el-dialog .el-button')).map((b) =>
      b.textContent?.trim(),
    )
    expect(btns).not.toContain('保存')
    expect(btns).not.toContain('+ 添加明细行')
    // 非草稿也不应有提交/批准（APPROVED 终态无流转按钮）
    expect(btns).not.toContain('提交')
  })

  it('无权限时不显示批准按钮', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as any
    // 关闭权限后打开 SUBMITTED 单：批准按钮应因无 purchase_order.approve 而隐藏
    authState.can = false
    await vm.openEdit(submittedPO)
    await flushPromises()
    const approveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '批准',
    )
    expect(approveBtn).toBeFalsy()
  })
})
