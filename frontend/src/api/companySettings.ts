import { http } from './http'
import type { CompanySettings, CompanySettingsUpdate } from '@/types/platform'

// 后端路由前缀 /company-settings（见 backend/app/routers/company_settings.py）。
export const getCompanySettings = () =>
  http.get<CompanySettings>('/company-settings').then((r) => r.data)

export const updateCompanySettings = (payload: CompanySettingsUpdate) =>
  http.put<CompanySettings>('/company-settings', payload).then((r) => r.data)
