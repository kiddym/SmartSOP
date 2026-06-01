import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/api/http', () => ({ http: { get, post } }))

import { fetchMe, login, refresh, register } from '@/api/auth'

describe('api/auth', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
  })

  it('login POST /auth/login 并返回 TokenPair', async () => {
    post.mockResolvedValue({ data: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' } })
    const res = await login({ email: 'x@y.com', password: 'pw12345678' })
    expect(post).toHaveBeenCalledWith('/auth/login', { email: 'x@y.com', password: 'pw12345678' }, { skipErrorToast: true })
    expect(res.access_token).toBe('a')
  })

  it('register POST /auth/register', async () => {
    post.mockResolvedValue({ data: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' } })
    const res = await register({ company_name: 'Acme', email: 'x@y.com', password: 'pw12345678', name: 'Neo' })
    expect(post).toHaveBeenCalledWith('/auth/register', {
      company_name: 'Acme', email: 'x@y.com', password: 'pw12345678', name: 'Neo',
    }, { skipErrorToast: true })
    expect(res.refresh_token).toBe('r')
  })

  it('refresh POST /auth/refresh 并包装 { refresh_token }', async () => {
    post.mockResolvedValue({ data: { access_token: 'a2', refresh_token: 'r2', token_type: 'bearer' } })
    const res = await refresh('r')
    expect(post).toHaveBeenCalledWith('/auth/refresh', { refresh_token: 'r' }, { skipErrorToast: true })
    expect(res.access_token).toBe('a2')
  })

  it('fetchMe GET /auth/me', async () => {
    get.mockResolvedValue({ data: { id: '1', email: 'x@y.com', name: 'Neo', company_id: 'c1', role_code: 'admin', permissions: ['user.view'] } })
    const me = await fetchMe()
    expect(get).toHaveBeenCalledWith('/auth/me', { skipErrorToast: true })
    expect(me.permissions).toEqual(['user.view'])
  })
})
