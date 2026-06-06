import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import * as authStorage from '@/utils/authStorage'

declare module 'axios' {
  // 按请求关闭统一错误 toast（用于"预期内"的失败，如可选资源 404）。
  export interface AxiosRequestConfig {
    skipErrorToast?: boolean
  }
}

export interface ApiErrorDetail {
  code: string
  message: string
  field?: string | null
}

export const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// —— 请求拦截：注入 access token —— //
function onRequest(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const token = authStorage.getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
}
http.interceptors.request.use(onRequest)

// —— 401 单飞续期 —— //
let refreshing: Promise<string> | null = null

// 用 doRefresh 注入便于测试；生产调用 performRefresh。
async function refreshOn401(doRefresh: () => Promise<string>): Promise<string> {
  if (!refreshing) {
    refreshing = doRefresh().finally(() => { refreshing = null })
  }
  return refreshing
}

async function performRefresh(): Promise<string> {
  const rt = authStorage.getRefreshToken()
  if (!rt) throw new Error('no refresh token')
  // 直发，不经 api/auth（避免循环依赖）
  const { data } = await http.post<{ access_token: string; refresh_token: string }>(
    '/auth/refresh', { refresh_token: rt }, { skipErrorToast: true },
  )
  authStorage.setAccessToken(data.access_token)
  authStorage.setRefreshToken(data.refresh_token)
  return data.access_token
}

function redirectToLogin(): void {
  authStorage.clearTokens()
  // 已在登录页则不再跳转：否则登录页上的 401（如通知轮询）会把当前含 redirect 的整 URL
  // 再次 encode 拼进新的 redirect，层层自嵌套 + 逐层转义直至 431/页面崩溃（死循环）。
  if (window.location.pathname === '/login') return
  const redirect = encodeURIComponent(window.location.pathname + window.location.search)
  window.location.assign(`/login?redirect=${redirect}`)
}

// 测试钩子
export const __test_onRequest = onRequest
export const __test_refreshOn401 = refreshOn401

// 统一错误提示 + 401 续期：解析后端 {detail:{code,message}} 信封并 toast；仍向调用方 reject。
http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status
    const original = error?.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const isRefreshCall = original?.url?.includes('/auth/refresh')

    if (status === 401 && original && !original._retried && !isRefreshCall) {
      original._retried = true
      try {
        const newAccess = await refreshOn401(performRefresh)
        original.headers.set('Authorization', `Bearer ${newAccess}`)
        return http(original)
      } catch {
        redirectToLogin()
        return Promise.reject(error)
      }
    }

    if (!error?.config?.skipErrorToast) {
      const detail = error?.response?.data?.detail as ApiErrorDetail | undefined
      ElMessage.error(detail?.message ?? '请求失败，请稍后重试')
    }
    return Promise.reject(error)
  },
)

/**
 * 真正的跨标签冲突：后端 If-Match 校验通过但 revision 已变（409 VERSION_CONFLICT）。
 * 注意：412 仅表示缺/坏 If-Match 标头（编程错误），不算冲突，故返回 false。
 */
export function isVersionConflict(err: unknown): boolean {
  const r = (err as { response?: { status?: number; data?: { detail?: { code?: string } } } })?.response
  return r?.status === 409 || r?.data?.detail?.code === 'VERSION_CONFLICT'
}

/** 取后端错误信封里的 message（供调用方自管 toast 的场景使用）。 */
export function errorMessage(err: unknown): string | undefined {
  return (err as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail?.message
}

/** 套餐未包含该功能（后端 402 + FEATURE_LOCKED）：供前端展示「升级订阅」引导而非误判为空数据。 */
export function isFeatureLocked(err: unknown): boolean {
  const r = (err as { response?: { status?: number; data?: { detail?: { code?: string } } } })?.response
  return r?.status === 402 || r?.data?.detail?.code === 'FEATURE_LOCKED'
}
