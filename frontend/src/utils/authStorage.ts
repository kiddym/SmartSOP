// token 存储底座：access 仅内存（不落盘，抗 XSS 持久窃取）；refresh 落 localStorage 以便刷新页恢复。
// http.ts 只依赖本模块读 token，避免 http→store 循环依赖。

const REFRESH_KEY = 'cmms.refresh_token'

let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function setRefreshToken(token: string | null): void {
  if (token === null) localStorage.removeItem(REFRESH_KEY)
  else localStorage.setItem(REFRESH_KEY, token)
}

export function clearTokens(): void {
  accessToken = null
  localStorage.removeItem(REFRESH_KEY)
}
