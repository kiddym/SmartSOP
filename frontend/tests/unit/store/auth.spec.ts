import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({ login: vi.fn(), register: vi.fn(), refresh: vi.fn(), fetchMe: vi.fn() }))
vi.mock('@/api/auth', () => api)
const storage = vi.hoisted(() => ({
  setAccessToken: vi.fn(), setRefreshToken: vi.fn(), getRefreshToken: vi.fn(), clearTokens: vi.fn(),
}))
vi.mock('@/utils/authStorage', () => storage)

import { useAuthStore } from '@/store/auth'

const ME = { id: '1', email: 'x@y.com', name: 'Neo', company_id: 'c1', role_code: 'admin', permissions: ['user.view'] }

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    Object.values(api).forEach((f) => f.mockReset())
    Object.values(storage).forEach((f) => f.mockReset())
  })

  it('login 成功：写 token + loadMe + isAuthenticated', async () => {
    api.login.mockResolvedValue({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    api.fetchMe.mockResolvedValue(ME)
    const s = useAuthStore()
    await s.login({ email: 'x@y.com', password: 'pw12345678' })
    expect(storage.setAccessToken).toHaveBeenCalledWith('a')
    expect(storage.setRefreshToken).toHaveBeenCalledWith('r')
    expect(s.user?.email).toBe('x@y.com')
    expect(s.isAuthenticated).toBe(true)
    expect(s.permissionCodes).toEqual(['user.view'])
  })

  it('hasPermission：super_admin 全通过；普通角色按码', async () => {
    api.fetchMe.mockResolvedValue({ ...ME, role_code: 'super_admin', permissions: [] })
    api.login.mockResolvedValue({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    const s = useAuthStore()
    await s.login({ email: 'x@y.com', password: 'pw12345678' })
    expect(s.hasPermission('anything.at.all')).toBe(true)
  })

  it('hasPermission：普通角色按权限码判定', async () => {
    api.fetchMe.mockResolvedValue(ME) // role_code 'admin', permissions ['user.view']
    api.login.mockResolvedValue({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    const s = useAuthStore()
    await s.login({ email: 'x@y.com', password: 'pw12345678' })
    expect(s.hasPermission('user.view')).toBe(true)
    expect(s.hasPermission('user.delete')).toBe(false)
  })

  it('logout 清 token 与身份', async () => {
    const s = useAuthStore()
    s.user = ME
    s.logout()
    expect(storage.clearTokens).toHaveBeenCalled()
    expect(s.user).toBeNull()
    expect(s.isAuthenticated).toBe(false)
  })

  it('bootstrap：无 refresh → 未登录、ready', async () => {
    storage.getRefreshToken.mockReturnValue(null)
    const s = useAuthStore()
    await s.bootstrap()
    expect(s.isAuthenticated).toBe(false)
    expect(api.refresh).not.toHaveBeenCalled()
  })

  it('bootstrap：有 refresh → 换 access + loadMe 恢复会话（且幂等）', async () => {
    storage.getRefreshToken.mockReturnValue('r')
    api.refresh.mockResolvedValue({ access_token: 'a2', refresh_token: 'r2', token_type: 'bearer' })
    api.fetchMe.mockResolvedValue(ME)
    const s = useAuthStore()
    await Promise.all([s.bootstrap(), s.bootstrap()]) // 幂等：只跑一次
    expect(api.refresh).toHaveBeenCalledTimes(1)
    expect(s.isAuthenticated).toBe(true)
  })
})
