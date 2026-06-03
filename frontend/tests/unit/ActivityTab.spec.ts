import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { la, ac } = vi.hoisted(() => ({ la: vi.fn(), ac: vi.fn() }))
vi.mock('@/api/workOrders', () => ({ listWorkOrderActivities: la, addWorkOrderComment: ac }))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn().mockResolvedValue([{ id: 'u1', name: '张三' }]),
}))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => authState.can }) }))

import ActivityTab from '@/components/workorder/ActivityTab.vue'

function mountTab() {
  return mount(ActivityTab, {
    props: { workOrderId: 'w1' },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  la.mockReset().mockResolvedValue([
    {
      id: 'a1',
      activity_type: 'STATUS_CHANGE',
      actor_user_id: 'u1',
      from_status: 'OPEN',
      to_status: 'IN_PROGRESS',
      comment: '',
      created_at: '2026-06-01T00:00:00',
    },
    {
      id: 'a2',
      activity_type: 'COMMENT',
      actor_user_id: 'u1',
      from_status: null,
      to_status: null,
      comment: '已开始',
      created_at: '2026-06-01T01:00:00',
    },
  ])
  ac.mockReset().mockResolvedValue({})
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('ActivityTab', () => {
  it('加载并渲染活动时间线', async () => {
    const w = mountTab()
    await flushPromises()
    expect(la).toHaveBeenCalledWith('w1')
    expect(w.text()).toContain('已开始') // comment
    expect(w.text()).toContain('待处理') // from OPEN 中文
    expect(w.text()).toContain('进行中') // to IN_PROGRESS 中文
  })

  it('发评论调 addWorkOrderComment 并重拉', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.commentText = '检查完毕'
    await vm.submitComment()
    await flushPromises()
    expect(ac).toHaveBeenCalledWith('w1', { comment: '检查完毕' })
    expect(la).toHaveBeenCalledTimes(2)
  })

  it('空评论不调用', async () => {
    const w = mountTab()
    await flushPromises()
    const vm = w.vm as any
    vm.commentText = '   '
    await vm.submitComment()
    expect(ac).not.toHaveBeenCalled()
  })
})
