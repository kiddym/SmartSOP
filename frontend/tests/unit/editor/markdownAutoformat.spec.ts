import { describe, it, expect } from 'vitest'
import { detectBlockTrigger, detectInlineTrigger } from '@/components/editor/markdownAutoformat'

describe('detectBlockTrigger', () => {
  it('bullet markers -, *, +', () => {
    expect(detectBlockTrigger('-')).toEqual({ type: 'bulleted', deleteLen: 1 })
    expect(detectBlockTrigger('*')).toEqual({ type: 'bulleted', deleteLen: 1 })
    expect(detectBlockTrigger('+')).toEqual({ type: 'bulleted', deleteLen: 1 })
  })
  it('numbered markers 1. and 12.', () => {
    expect(detectBlockTrigger('1.')).toEqual({ type: 'numbered', deleteLen: 2 })
    expect(detectBlockTrigger('12.')).toEqual({ type: 'numbered', deleteLen: 3 })
  })
  it('blockquote marker >', () => {
    expect(detectBlockTrigger('>')).toEqual({ type: 'blockquote', deleteLen: 1 })
  })
  it('null when not at block start or unsupported', () => {
    expect(detectBlockTrigger(' -')).toBeNull()
    expect(detectBlockTrigger('x-')).toBeNull()
    expect(detectBlockTrigger('#')).toBeNull()
    expect(detectBlockTrigger('1')).toBeNull()
    expect(detectBlockTrigger('1)')).toBeNull()
    expect(detectBlockTrigger('')).toBeNull()
  })
})

describe('detectInlineTrigger', () => {
  it('bold **x**', () => {
    expect(detectInlineTrigger('**bold**')).toEqual({
      mark: 'bold', openStart: 0, innerStart: 2, innerEnd: 6, closeEnd: 8,
    })
  })
  it('italic *x* and _x_', () => {
    expect(detectInlineTrigger('*it*')).toEqual({ mark: 'italic', openStart: 0, innerStart: 1, innerEnd: 3, closeEnd: 4 })
    expect(detectInlineTrigger('_it_')).toEqual({ mark: 'italic', openStart: 0, innerStart: 1, innerEnd: 3, closeEnd: 4 })
  })
  it('code `x`', () => {
    expect(detectInlineTrigger('`c`')).toEqual({ mark: 'code', openStart: 0, innerStart: 1, innerEnd: 2, closeEnd: 3 })
  })
  it('does NOT fire mid-bold (single closing * inside **…*)', () => {
    expect(detectInlineTrigger('**bold*')).toBeNull()
  })
  it('null for incomplete / empty / non-delimiter end', () => {
    expect(detectInlineTrigger('**bold')).toBeNull()
    expect(detectInlineTrigger('``')).toBeNull()
    expect(detectInlineTrigger('**')).toBeNull()
    expect(detectInlineTrigger('plain')).toBeNull()
    expect(detectInlineTrigger('* x *')).toMatchObject({ mark: 'italic' })
  })
  it('respects leading text (offsets relative to string start)', () => {
    expect(detectInlineTrigger('say `hi`')).toEqual({ mark: 'code', openStart: 4, innerStart: 5, innerEnd: 7, closeEnd: 8 })
  })
})
