import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const woApi = vi.hoisted(() => ({ getExecution: vi.fn(), patchStepResult: vi.fn() }))
vi.mock('@/api/workOrders', () => woApi)
const attApi = vi.hoisted(() => ({
  listEntityAttachments: vi.fn(),
  uploadEntityAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
  downloadAttachment: vi.fn(),
}))
vi.mock('@/api/attachments', () => attApi)
vi.mock('@/api/users', () => ({ listUsers: vi.fn().mockResolvedValue([]) }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))

import ExecutionTab from '@/components/workorder/ExecutionTab.vue'

const EXEC = {
  procedure: { id: 'p', group_id: 'g', code: 'S', name: 'P', version: 1 },
  outline: [],
  steps: [{
    id: 'sr1', node_id: 'n1', node_code: 'S1', node_sort_order: 1,
    input_schema: { type: 'UPLOAD', required: true }, response: {},
    is_done: false, done_by_user_id: null, done_at: null, notes: '', attachment_count: 0,
  }],
}

beforeEach(() => {
  setActivePinia(createPinia())
  woApi.getExecution.mockReset().mockResolvedValue(EXEC)
  attApi.listEntityAttachments.mockReset().mockResolvedValue([])
  attApi.uploadEntityAttachment.mockReset().mockResolvedValue({ id: 'a1', file_name: 'x.png' })
  attApi.deleteAttachment.mockReset().mockResolvedValue(undefined)
})

describe('ExecutionTab attachments', () => {
  it('UPLOAD 步骤渲染上传控件并按 step 拉附件', async () => {
    const w = mount(ExecutionTab, { props: { workOrderId: 'wo1' }, global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(attApi.listEntityAttachments).toHaveBeenCalledWith('work_order_step_result', 'sr1')
    expect(w.find('.el-upload').exists()).toBe(true)
  })
})
