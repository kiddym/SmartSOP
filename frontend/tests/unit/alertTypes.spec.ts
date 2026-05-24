import { describe, it, expect } from 'vitest'
import { FORM_TYPES } from '@/types/node'
import { FORM_TYPE_META, isAlertType, isRichTextType, ALERT_TYPES } from '@/utils/editor'

describe('alert form types', () => {
  it('FORM_TYPES 含 NOTE/CAUTION/WARNING', () => {
    expect(FORM_TYPES).toEqual(expect.arrayContaining(['NOTE', 'CAUTION', 'WARNING']))
  })
  it('isAlertType 仅对三警示为真', () => {
    expect(ALERT_TYPES).toEqual(['NOTE', 'CAUTION', 'WARNING'])
    expect(isAlertType('WARNING')).toBe(true)
    expect(isAlertType('NUMBER')).toBe(false)
  })
  it('isRichTextType 含 COMMON 与三警示', () => {
    expect(isRichTextType('COMMON')).toBe(true)
    expect(isRichTextType('NOTE')).toBe(true)
    expect(isRichTextType('NUMBER')).toBe(false)
  })
  it('三警示有 label 与配色', () => {
    expect(FORM_TYPE_META.NOTE.label).toBe('注意')
    expect(FORM_TYPE_META.CAUTION.color).toBe('orange')
    expect(FORM_TYPE_META.WARNING.color).toBe('red')
  })
})
