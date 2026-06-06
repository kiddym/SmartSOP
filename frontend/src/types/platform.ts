// 平台管理类型（与后端 app/schemas 平台相关 schema 对齐）。

export type UserStatus = 'active' | 'disabled'

export interface UserRead {
  id: string
  email: string
  name: string
  status: UserStatus
  role_id: string | null
  locale: string
  phone: string | null
  job_title: string | null
  rate: string | null
  avatar_url: string | null
  email_verified?: boolean
  last_login_at: string | null
  created_at: string
}

// 自助资料编辑（仅白名单字段，对齐后端 SelfProfileUpdate）。
export interface SelfProfileUpdate {
  name?: string
  phone?: string | null
  job_title?: string | null
  avatar_url?: string | null
  locale?: string
}

export interface UserCreate {
  email: string
  password: string
  name: string
  role_id?: string | null
}

export interface UserInvite {
  email: string
  role_id?: string | null
}

export interface UserUpdate {
  name?: string
  role_id?: string | null
  status?: UserStatus
  password?: string
}

export interface InviteResult {
  id: string
  email: string
  status: string
}

export interface RoleRead {
  id: string
  code: string
  name: string
  is_builtin: boolean
  permissions: string[]
}

export interface RoleCreate {
  code: string
  name: string
  permissions: string[]
}

export interface RoleUpdate {
  name?: string
  permissions?: string[]
}

export interface TeamRead {
  id: string
  name: string
  description: string
  member_ids: string[]
}

export interface TeamCreate {
  name: string
  description?: string
}

export interface TeamUpdate {
  name?: string
  description?: string
}

export interface CompanySettings {
  date_format: string
  timezone: string
  default_currency_code: string
  auto_assign: boolean
  // 导航模块显隐开关（后端默认 true）。某项为 false 时侧栏隐藏对应入口。
  show_requests: boolean
  show_locations: boolean
  show_meters: boolean
  show_vendors_customers: boolean
}

export type CompanySettingsUpdate = Partial<CompanySettings>

export interface Currency {
  id: string
  code: string
  name: string
  symbol: string
}

export interface CurrencyCreate {
  code: string
  name: string
  symbol?: string
}

export interface PermissionItem {
  code: string
  label: string
}

export interface PermissionGroup {
  group: string
  permissions: PermissionItem[]
}
