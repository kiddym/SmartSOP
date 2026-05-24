import { describe, expect, it } from 'vitest'
import {
  FORM_TYPE_META,
  computeFallback,
  firstLinePreview,
  getAddButtonState,
  htmlToText,
  isTempId,
  genTempId,
} from '@/utils/editor'
import { FORM_TYPES } from '@/types/node'

describe('getAddButtonState — Q25 互斥', () => {
  it('空 parent 三种皆可加', () => {
    expect(getAddButtonState([])).toEqual({
      canAddChapter: true,
      canAddContent: true,
      canAddStep: true,
    })
  })
  it('已有 step → 只能加 step', () => {
    expect(getAddButtonState(['step'])).toEqual({
      canAddChapter: false,
      canAddContent: false,
      canAddStep: true,
    })
  })
  it('已有 chapter → 不能加 step', () => {
    const s = getAddButtonState(['chapter'])
    expect(s.canAddStep).toBe(false)
    expect(s.canAddChapter).toBe(true)
    expect(s.canAddContent).toBe(true)
  })
  it('已有 content → 不能加 step', () => {
    expect(getAddButtonState(['content']).canAddStep).toBe(false)
  })
  it('chapter + content 混排 → 不能加 step', () => {
    expect(getAddButtonState(['chapter', 'content']).canAddStep).toBe(false)
  })
})

describe('htmlToText / firstLinePreview', () => {
  it('剥离标签、块级转行、解码实体', () => {
    expect(htmlToText('<p>第一段</p><p>第二段</p>')).toBe('第一段\n第二段\n')
    expect(htmlToText('A &amp; B')).toBe('A & B')
    expect(htmlToText('a<br>b')).toBe('a\nb')
  })
  it('取首个非空行', () => {
    expect(firstLinePreview('\n  第一行  \n第二行')).toBe('第一行')
  })
  it('超长截断加省略号', () => {
    const long = 'x'.repeat(60)
    const out = firstLinePreview(long, 50)
    expect(out.length).toBe(51)
    expect(out.endsWith('…')).toBe(true)
  })
})

describe('computeFallback', () => {
  it('章节恒为未命名提示', () => {
    expect(computeFallback('chapter', '<p>正文</p>')).toBe('(未命名章节)')
  })
  it('内容取首行预览，空则占位', () => {
    expect(computeFallback('content', '<p>适用范围</p>')).toBe('适用范围')
    expect(computeFallback('content', '')).toBe('(空内容块)')
  })
  it('步骤取首行预览，空则占位', () => {
    expect(computeFallback('step', '<p>拧紧螺栓</p>')).toBe('拧紧螺栓')
    expect(computeFallback('step', '')).toBe('(空步骤)')
  })
})

describe('FORM_TYPE_META', () => {
  it('覆盖全部类型', () => {
    expect(Object.keys(FORM_TYPE_META).sort()).toEqual([...FORM_TYPES].sort())
  })
  it('色组合法', () => {
    const ok = new Set(['gray', 'blue', 'purple', 'cyan', 'orange', 'red'])
    for (const t of FORM_TYPES) expect(ok.has(FORM_TYPE_META[t].color)).toBe(true)
  })
})

describe('临时 id', () => {
  it('genTempId 带 temp- 前缀且唯一', () => {
    const a = genTempId()
    const b = genTempId()
    expect(isTempId(a)).toBe(true)
    expect(a).not.toBe(b)
  })
  it('真实 id 非 temp', () => {
    expect(isTempId('real-uuid-123')).toBe(false)
  })
})
