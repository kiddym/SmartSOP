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
