import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authStorage from '@/utils/authStorage'
import { __test_onRequest, __test_refreshOn401, http } from '@/api/http'

describe('http auth 拦截', () => {
  beforeEach(() => {
    authStorage.clearTokens()
  })

  it('请求拦截器注入 Authorization', () => {
    authStorage.setAccessToken('acc-9')
    const cfg = __test_onRequest({ headers: {} } as never)
    expect((cfg.headers as Record<string, string>).Authorization).toBe('Bearer acc-9')
  })

  it('无 access 时不加 Authorization', () => {
    const cfg = __test_onRequest({ headers: {} } as never)
    expect((cfg.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('401 单飞：并发只发一个 refresh', async () => {
    authStorage.setRefreshToken('r')
    const doRefresh = vi.fn(async () => { await Promise.resolve(); return 'new-acc' })
    const [a, b] = await Promise.all([__test_refreshOn401(doRefresh), __test_refreshOn401(doRefresh)])
    expect(doRefresh).toHaveBeenCalledTimes(1)
    expect(a).toBe('new-acc')
    expect(b).toBe('new-acc')
  })

  it('端到端：受保护请求 401 → 自动 refresh → 带新 token 重试成功', async () => {
    authStorage.setAccessToken('stale')
    authStorage.setRefreshToken('r1')

    const seen: { url?: string; auth?: unknown }[] = []
    const originalAdapter = http.defaults.adapter
    http.defaults.adapter = async (config) => {
      const auth = config.headers?.Authorization
      seen.push({ url: config.url, auth })
      if (config.url === '/auth/refresh') {
        return {
          data: { access_token: 'fresh', refresh_token: 'r2', token_type: 'bearer' },
          status: 200, statusText: 'OK', headers: {}, config,
        }
      }
      if (config.url === '/protected' && auth === 'Bearer stale') {
        // 首次：旧 token → 401
        return Promise.reject({
          config, response: { status: 401, data: {}, headers: {}, statusText: 'Unauthorized', config },
          isAxiosError: true, message: '401', name: 'AxiosError',
        })
      }
      // 重试：带新 token → 200
      return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config }
    }

    try {
      const res = await http.get('/protected')
      expect(res.data).toEqual({ ok: true })
      // 自动续期写入了新 token
      expect(authStorage.getAccessToken()).toBe('fresh')
      // 重试请求带的是新 token
      const retry = seen.find((s) => s.url === '/protected' && s.auth === 'Bearer fresh')
      expect(retry).toBeTruthy()
      // 只发了一次 refresh
      expect(seen.filter((s) => s.url === '/auth/refresh')).toHaveLength(1)
    } finally {
      http.defaults.adapter = originalAdapter
    }
  })
})
