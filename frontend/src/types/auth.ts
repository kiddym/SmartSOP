export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LoginPayload {
  email: string
  password: string
  company_slug?: string
}

export interface RegisterPayload {
  company_name: string
  email: string
  password: string
  name: string
}

export interface CurrentUser {
  id: string
  email: string
  name: string
  company_id: string
  role_code: string | null
  permissions: string[]
  email_verified?: boolean
}

export interface SwitchableAccount {
  company_id: string
  company_name: string
  company_slug: string
  user_id: string
}
