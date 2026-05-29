import { describe, expect, it } from 'vitest'
import { isVersionConflict, errorMessage } from '@/api/http'

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
