import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import ProfileView from '@/views/account/ProfileView.vue'
import { useAuthStore } from '@/store/auth'
import * as usersApi from '@/api/users'
import type { UserRead } from '@/types/platform'

vi.mock('@/api/users', () => ({
  getMyProfile: vi.fn(),
  updateMyProfile: vi.fn(),
}))

const mockedUsers = vi.mocked(usersApi)

const baseUser: UserRead = {
  id: 'u1',
  email: 'me@acme.com',
  name: 'Neo',
  status: 'active',
  role_id: null,
  locale: 'zh-CN',
  phone: '12345',
  job_title: 'Operator',
  rate: '42.0000',
  avatar_url: null,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
}

function mountView() {
  return mount(ProfileView, { global: { plugins: [ElementPlus, i18n] } })
}

describe('ProfileView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockedUsers.getMyProfile.mockResolvedValue({ ...baseUser })
    mockedUsers.updateMyProfile.mockResolvedValue({ ...baseUser })
  })

  it('加载并回显当前资料', async () => {
    const w = mountView()
    await flushPromises()
    expect(mockedUsers.getMyProfile).toHaveBeenCalled()
    // el-input passes data-test through to the native <input> element directly.
    expect((w.find('[data-test="name"]').element as HTMLInputElement).value).toBe('Neo')
    expect((w.find('[data-test="phone"]').element as HTMLInputElement).value).toBe('12345')
    expect((w.find('[data-test="email"]').element as HTMLInputElement).value).toBe('me@acme.com')
    // email/rate 只读
    expect((w.find('[data-test="email"]').element as HTMLInputElement).disabled).toBe(true)
  })

  it('保存调用 updateMyProfile 并触发 loadMe', async () => {
    const auth = useAuthStore()
    const loadMeSpy = vi.spyOn(auth, 'loadMe').mockResolvedValue()
    mockedUsers.updateMyProfile.mockResolvedValue({ ...baseUser, name: 'Trinity' })

    const w = mountView()
    await flushPromises()

    await w.find('[data-test="name"]').setValue('Trinity')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(mockedUsers.updateMyProfile).toHaveBeenCalledTimes(1)
    const payload = mockedUsers.updateMyProfile.mock.calls[0][0]
    expect(payload.name).toBe('Trinity')
    // 不允许自助改的字段不应出现在 payload 中
    expect(payload).not.toHaveProperty('role_id')
    expect(payload).not.toHaveProperty('status')
    expect(payload).not.toHaveProperty('rate')
    expect(loadMeSpy).toHaveBeenCalled()
  })
})
