import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/store/auth'
import * as authApi from '@/api/auth'
import * as authStorage from '@/utils/authStorage'

describe('auth store logout', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('calls server logout then clears client state', async () => {
    const apiSpy = vi.spyOn(authApi, 'logout').mockResolvedValue()
    const clearSpy = vi.spyOn(authStorage, 'clearTokens').mockImplementation(() => {})
    const store = useAuthStore()
    store.user = { id: '1', email: 'a@a.com', name: 'A', company_id: 'c', role_code: null, permissions: [] } as never
    await store.logout()
    expect(apiSpy).toHaveBeenCalled()
    expect(clearSpy).toHaveBeenCalled()
    expect(store.user).toBeNull()
  })

  it('still clears client state if server logout fails', async () => {
    vi.spyOn(authApi, 'logout').mockRejectedValue(new Error('network'))
    const clearSpy = vi.spyOn(authStorage, 'clearTokens').mockImplementation(() => {})
    const store = useAuthStore()
    store.user = { id: '1' } as never
    await store.logout()
    expect(clearSpy).toHaveBeenCalled()
    expect(store.user).toBeNull()
  })
})
