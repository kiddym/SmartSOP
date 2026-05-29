import { describe, expect, it } from 'vitest'
import { FORM_TYPE_META } from '@/utils/editor'
import { FORM_TYPES } from '@/types/node'

describe('FORM_TYPE_META', () => {
  it('覆盖全部类型', () => {
    expect(Object.keys(FORM_TYPE_META).sort()).toEqual([...FORM_TYPES].sort())
  })
  it('色组合法', () => {
    const ok = new Set(['gray', 'blue', 'purple', 'cyan', 'orange', 'red'])
    for (const t of FORM_TYPES) expect(ok.has(FORM_TYPE_META[t].color)).toBe(true)
  })
})
