import { beforeEach, describe, expect, it } from 'vitest'
import * as authStorage from '@/utils/authStorage'

describe('authStorage', () => {
  beforeEach(() => {
    localStorage.clear()
    authStorage.setAccessToken(null)
  })

  it('access token 只在内存、不落 localStorage', () => {
    authStorage.setAccessToken('acc-1')
    expect(authStorage.getAccessToken()).toBe('acc-1')
    expect(localStorage.getItem('cmms.refresh_token')).toBeNull()
  })

  it('refresh token 落 localStorage 并可读回', () => {
    authStorage.setRefreshToken('ref-1')
    expect(authStorage.getRefreshToken()).toBe('ref-1')
    expect(localStorage.getItem('cmms.refresh_token')).toBe('ref-1')
  })

  it('clearTokens 同时清内存与 localStorage', () => {
    authStorage.setAccessToken('a')
    authStorage.setRefreshToken('r')
    authStorage.clearTokens()
    expect(authStorage.getAccessToken()).toBeNull()
    expect(authStorage.getRefreshToken()).toBeNull()
  })
})
