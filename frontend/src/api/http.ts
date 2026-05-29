import axios, { type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

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

// 统一错误提示：解析后端 {detail:{code,message}} 信封并 toast；仍向调用方 reject。
http.interceptors.response.use(
  (response) => response,
  (error) => {
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
