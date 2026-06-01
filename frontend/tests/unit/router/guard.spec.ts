import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { authGuard } from '@/router/guard'
import { useAuthStore } from '@/store/auth'

describe('authGuard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('未登录访问受保护路由 → 重定向 /login 带 redirect', async () => {
    const s = useAuthStore()
    vi.spyOn(s, 'bootstrap').mockResolvedValue()
    const to = { path: '/folders', fullPath: '/folders', meta: { requiresAuth: true } } as never
    const res = await authGuard(to, {} as never)
    expect(res).toEqual({ name: 'login', query: { redirect: '/folders' } })
  })

  it('已登录访问 /login → 重定向首页', async () => {
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'n', company_id: 'c', role_code: 'admin', permissions: [] }
    vi.spyOn(s, 'bootstrap').mockResolvedValue()
    const to = { path: '/login', fullPath: '/login', name: 'login', meta: {} } as never
    const res = await authGuard(to, {} as never)
    expect(res).toEqual({ path: '/' })
  })

  it('已登录访问受保护路由 → 放行(true)', async () => {
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'n', company_id: 'c', role_code: 'admin', permissions: [] }
    vi.spyOn(s, 'bootstrap').mockResolvedValue()
    const to = { path: '/folders', fullPath: '/folders', meta: { requiresAuth: true } } as never
    const res = await authGuard(to, {} as never)
    expect(res).toBe(true)
  })

  it('未登录访问公开路由(login) → 放行(true)', async () => {
    const s = useAuthStore()
    vi.spyOn(s, 'bootstrap').mockResolvedValue()
    const to = { path: '/login', fullPath: '/login', name: 'login', meta: {} } as never
    const res = await authGuard(to, {} as never)
    expect(res).toBe(true)
  })
})
