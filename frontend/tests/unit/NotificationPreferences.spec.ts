import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  getPreference: vi.fn(),
  putPreference: vi.fn(),
  getUnreadCount: vi.fn(),
  listNotifications: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
}))
vi.mock('@/api/notifications', () => api)
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() } }))

import NotificationPreferences from '@/components/notifications/NotificationPreferences.vue'

const slot = { template: '<div><slot /></div>' }
const stubs = { 'el-switch': true, 'el-button': slot, 'el-form': slot, 'el-form-item': slot }

describe('NotificationPreferences', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.getPreference.mockReset().mockResolvedValue({ email_enabled: true, disabled_types: ['WO_ASSIGNED'] })
    api.putPreference.mockReset().mockImplementation(async (p) => p)
  })

  it('挂载加载偏好', async () => {
    mount(NotificationPreferences, { global: { stubs } })
    await flushPromises()
    expect(api.getPreference).toHaveBeenCalled()
  })

  it('保存把关闭的类型写入 disabled_types', async () => {
    const w = mount(NotificationPreferences, { global: { stubs } })
    await flushPromises()
    await (w.vm as unknown as { toggleType: (c: string, on: boolean) => void; save: () => Promise<void> }).toggleType('WO_STATUS_CHANGED', false)
    await (w.vm as unknown as { save: () => Promise<void> }).save()
    expect(api.putPreference).toHaveBeenCalled()
    const arg = api.putPreference.mock.calls[0][0]
    expect(arg.disabled_types).toContain('WO_STATUS_CHANGED')
    expect(arg.disabled_types).toContain('WO_ASSIGNED')
  })
})
