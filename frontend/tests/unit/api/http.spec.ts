import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { http, isVersionConflict, errorMessage } from '@/api/http'

describe('http client', () => {
  it('sends cookies so <img> asset requests authenticate', () => {
    expect(http.defaults.withCredentials).toBe(true)
  })
})

describe('isVersionConflict', () => {
  it('true on HTTP 409', () => {
    expect(isVersionConflict({ response: { status: 409 } })).toBe(true)
  })
  it('true on VERSION_CONFLICT code even without 409 status', () => {
    expect(isVersionConflict({ response: { data: { detail: { code: 'VERSION_CONFLICT' } } } })).toBe(true)
  })
  it('false on 412 (missing If-Match — a programming error, not a race)', () => {
    expect(isVersionConflict({ response: { status: 412, data: { detail: { code: 'IF_MATCH_REQUIRED' } } } })).toBe(false)
  })
  it('false on unrelated errors / undefined', () => {
    expect(isVersionConflict({ response: { status: 500 } })).toBe(false)
    expect(isVersionConflict(undefined)).toBe(false)
  })
})

describe('errorMessage', () => {
  it('extracts detail.message', () => {
    expect(errorMessage({ response: { data: { detail: { message: 'boom' } } } })).toBe('boom')
  })
  it('undefined when absent', () => {
    expect(errorMessage(new Error('x'))).toBeUndefined()
  })
})

describe('redirectToLogin clears server cookie', () => {
  let assignSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    // 模块级 loggingOut 守卫跨测试持久化：第一个测试会把它置 true，导致第二个测试在
    // clearTokens 之后提前 return、不再发 logout / 不跳转，从而让断言失真。
    // 用 resetModules + 每测试动态 import 拿到全新模块实例（loggingOut 重置为 false），
    // 保证两个测试都真实地走完整路径。
    vi.resetModules()
    assignSpy = vi.fn()
    // jsdom: stub navigation + pathname
    Object.defineProperty(window, 'location', {
      value: { pathname: '/procedures', search: '', assign: assignSpy },
      writable: true,
      configurable: true,
    })
  })
  afterEach(() => vi.restoreAllMocks())

  it('calls POST /auth/logout and clears client tokens before redirecting', async () => {
    const { http: freshHttp, __test_redirectToLogin } = await import('@/api/http')
    const authStorage = await import('@/utils/authStorage')
    const postSpy = vi.spyOn(freshHttp, 'post').mockResolvedValue({ data: { status: 'ok' } } as never)
    const clearSpy = vi.spyOn(authStorage, 'clearTokens').mockImplementation(() => {})
    await __test_redirectToLogin()
    expect(clearSpy).toHaveBeenCalled()
    expect(postSpy).toHaveBeenCalledWith('/auth/logout', {}, expect.objectContaining({ skipErrorToast: true }))
    expect(assignSpy).toHaveBeenCalledWith(expect.stringContaining('/login?redirect='))
  })

  it('still redirects if the logout call fails (best-effort)', async () => {
    const { http: freshHttp, __test_redirectToLogin } = await import('@/api/http')
    const authStorage = await import('@/utils/authStorage')
    vi.spyOn(freshHttp, 'post').mockRejectedValue(new Error('network'))
    vi.spyOn(authStorage, 'clearTokens').mockImplementation(() => {})
    await __test_redirectToLogin()
    expect(assignSpy).toHaveBeenCalled()
  })
})
