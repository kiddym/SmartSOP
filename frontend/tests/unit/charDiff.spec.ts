import { describe, it, expect } from 'vitest'
import { htmlToText, charDiff } from '@/components/version/charDiff'

describe('htmlToText', () => {
  it('strips tags + unescapes entities; empty → ""', () => {
    expect(htmlToText('<p>目的</p><p>其余</p>')).toBe('目的其余')
    expect(htmlToText('<p>A &amp; B</p>')).toBe('A & B')
    expect(htmlToText('')).toBe('')
  })
})

describe('charDiff', () => {
  it('identical → one equal seg; empty → []', () => {
    expect(charDiff('abc', 'abc')).toEqual([{ type: 'equal', text: 'abc' }])
    expect(charDiff('', '')).toEqual([])
  })
  it('pure insertion (prefix + ins + suffix)', () => {
    expect(charDiff('公司股东', '公司创始股东')).toEqual([
      { type: 'equal', text: '公司' },
      { type: 'ins', text: '创始' },
      { type: 'equal', text: '股东' },
    ])
  })
  it('pure deletion', () => {
    expect(charDiff('公司创始股东', '公司股东')).toEqual([
      { type: 'equal', text: '公司' },
      { type: 'del', text: '创始' },
      { type: 'equal', text: '股东' },
    ])
  })
  it('replacement (del + ins, runs merged)', () => {
    expect(charDiff('公司所有股东', '公司创始股东')).toEqual([
      { type: 'equal', text: '公司' },
      { type: 'del', text: '所有' },
      { type: 'ins', text: '创始' },
      { type: 'equal', text: '股东' },
    ])
  })
  it('empty a → all ins; empty b → all del', () => {
    expect(charDiff('', 'abc')).toEqual([{ type: 'ins', text: 'abc' }])
    expect(charDiff('abc', '')).toEqual([{ type: 'del', text: 'abc' }])
  })
  it('size guard: huge fully-different middles degrade to [del, ins]', () => {
    const a = 'a'.repeat(1001)
    const b = 'b'.repeat(1001)
    expect(charDiff(a, b)).toEqual([
      { type: 'del', text: a },
      { type: 'ins', text: b },
    ])
  })
})
