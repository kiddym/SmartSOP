import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

const { lw, dw } = vi.hoisted(() => ({ lw: vi.fn(), dw: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ listWorkOrders: lw, deleteWorkOrder: dw }))
vi.mock('@/api/assets', () => ({
  listAssetsMini: vi.fn().mockResolvedValue([{ id: 'a1', name: '泵' }]),
}))
vi.mock('@/api/locations', () => ({
  listLocationsMini: vi.fn().mockResolvedValue([{ id: 'l1', name: '车间' }]),
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))
// FormDialog 与 category 对话框 stub，避免其内部 onMounted 拉取
vi.mock('@/components/workorder/WorkOrderFormDialog.vue', () => ({
  default: {
    name: 'WorkOrderFormDialog',
    props: ['visible', 'mode', 'editing'],
    emits: ['update:visible', 'saved'],
    template: '<div class="form-dialog-stub" />',
  },
}))
vi.mock('@/components/maintenance/WorkOrderCategoryManageDialog.vue', () => ({
  default: {
    name: 'WorkOrderCategoryManageDialog',
    props: ['visible'],
    emits: ['update:visible', 'changed'],
    template: '<div class="cat-dialog-stub" />',
  },
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import WorkOrdersView from '@/views/maintenance/WorkOrdersView.vue'

function mountView() {
  return mount(WorkOrdersView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

const wo = {
  id: 'w1',
  custom_id: 'WO-001',
  title: '泵检修',
  description: '',
  status: 'IN_PROGRESS',
  priority: 'HIGH',
  due_date: null,
  asset_id: 'a1',
  location_id: 'l1',
  primary_user_id: 'u1',
  procedure_id: null,
  procedure_group_id: null,
  completed_at: null,
  category_id: null,
  created_by_user_id: null,
  assignee_ids: [],
  team_ids: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  push.mockReset()
  lw.mockReset().mockResolvedValue([wo])
  dw.mockReset().mockResolvedValue(undefined)
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('WorkOrdersView', () => {
  it('加载并渲染工单 + 状态中文 + 资产/负责人名', async () => {
    const w = mountView()
    await flushPromises()
    expect(lw).toHaveBeenCalled()
    expect(w.text()).toContain('WO-001')
    expect(w.text()).toContain('泵检修')
    expect(w.text()).toContain('进行中')
    expect(w.text()).toContain('泵')
    expect(w.text()).toContain('张三')
  })

  it('点详情跳路由', async () => {
    const w = mountView()
    await flushPromises()
    const detailBtn = w.findAll('.el-button').find((b) => b.text() === '详情')
    await detailBtn!.trigger('click')
    expect(push).toHaveBeenCalledWith('/maintenance/work-orders/w1')
  })

  it('删除经确认调 deleteWorkOrder', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await flushPromises()
    expect(dw).toHaveBeenCalledWith('w1')
  })

  it('无权限隐藏新建工单按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建工单')).toBeFalsy()
  })

  it('过滤 procedure=false + status=OPEN → listWorkOrders 参数含 procedure_attached:false + status:OPEN', async () => {
    const w = mountView()
    await flushPromises()
    lw.mockClear()

    const vm = w.vm as any
    vm.filterProcedure = 'false'
    vm.filterStatus = 'OPEN'
    await vm.fetchWorkOrders()
    await flushPromises()

    const lastCall = lw.mock.calls[lw.mock.calls.length - 1][0]
    expect(lastCall).toMatchObject({ status: 'OPEN', procedure_attached: false })
  })
})
