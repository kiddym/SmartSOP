import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
  getUnreadCount: vi.fn(),
  getPreference: vi.fn(),
  putPreference: vi.fn(),
}))
vi.mock('@/api/notifications', () => api)
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

import NotificationCenterView from '@/views/notifications/NotificationCenterView.vue'

const slot = { template: '<div><slot /></div>' }
const stubs = {
  'el-tabs': slot, 'el-tab-pane': slot, 'el-radio-group': slot, 'el-radio-button': slot,
  'el-select': slot, 'el-option': slot, 'el-pagination': true, 'el-button': slot,
  'el-empty': true, 'el-switch': true, NotificationPreferences: true,
}

describe('NotificationCenterView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.listNotifications.mockReset().mockResolvedValue({
      items: [{ id: 'n1', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
        params: { custom_id: 'C-1', title: '巡检' }, actor_user_id: null, is_read: false,
        read_at: null, created_at: '2026-06-05T00:00:00' }],
      total: 1, page: 1, page_size: 20, total_pages: 1,
    })
    api.markAllRead.mockReset().mockResolvedValue({ updated: 1 })
    api.markRead.mockReset().mockResolvedValue({})
    api.getUnreadCount.mockReset().mockResolvedValue({ count: 0 })
  })

  it('挂载拉列表并渲染文案', async () => {
    const w = mount(NotificationCenterView, { global: { stubs } })
    await flushPromises()
    expect(api.listNotifications).toHaveBeenCalled()
    expect(w.text()).toContain('C-1')
  })

  it('切到未读过滤重新拉（is_read=false）', async () => {
    const w = mount(NotificationCenterView, { global: { stubs } })
    await flushPromises()
    await (w.vm as unknown as { setFilter: (v: string) => void }).setFilter('unread')
    await flushPromises()
    expect(api.listNotifications).toHaveBeenLastCalledWith(expect.objectContaining({ is_read: false }))
  })

  it('全部已读调用 api', async () => {
    const w = mount(NotificationCenterView, { global: { stubs } })
    await flushPromises()
    await (w.vm as unknown as { onMarkAll: () => Promise<void> }).onMarkAll()
    expect(api.markAllRead).toHaveBeenCalled()
  })
})
