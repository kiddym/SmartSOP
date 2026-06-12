import { http } from './http'
import type {
  CurrentUser,
  LoginPayload,
  RegisterPayload,
  SwitchableAccount,
  TokenPair,
} from '@/types/auth'

export const login = async (payload: LoginPayload): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/login', payload, { skipErrorToast: true })).data

export const register = async (payload: RegisterPayload): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/register', payload, { skipErrorToast: true })).data

export const refresh = async (refreshToken: string): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/refresh', { refresh_token: refreshToken }, { skipErrorToast: true })).data

export const fetchMe = async (): Promise<CurrentUser> =>
  (await http.get<CurrentUser>('/auth/me', { skipErrorToast: true })).data

export const forgotPassword = async (email: string, companySlug?: string): Promise<void> => {
  await http.post('/auth/forgot-password', { email, company_slug: companySlug || undefined }, { skipErrorToast: true })
}

export const resetPassword = async (token: string, newPassword: string): Promise<void> => {
  await http.post('/auth/reset-password', { token, new_password: newPassword }, { skipErrorToast: true })
}

export const changePassword = async (oldPassword: string, newPassword: string): Promise<void> => {
  await http.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword }, { skipErrorToast: true })
}

export const acceptInvite = async (token: string, name: string, password: string): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/accept-invite', { token, name, password }, { skipErrorToast: true })).data

export const listSwitchableAccounts = async (): Promise<SwitchableAccount[]> =>
  (await http.get<SwitchableAccount[]>('/auth/switchable-accounts')).data

export const switchAccount = async (companyId: string): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/switch-account', { company_id: companyId })).data

export const requestVerification = async (): Promise<void> => {
  await http.post('/auth/request-verification', {})
}

export const verifyEmail = async (token: string): Promise<void> => {
  await http.post('/auth/verify-email', { token }, { skipErrorToast: true })
}

export const logout = async (): Promise<void> => {
  await http.post('/auth/logout', {}, { skipErrorToast: true })
}
