import { describe, expect, it } from 'vitest'
import { formatCode, recomputeCodes } from '@/utils/editor'
import type { EditorChapter, EditorStep } from '@/types/node'

function ch(
  id: string,
  parentId: string | null,
  sort: number,
  opts: { skip?: boolean } = {},
): EditorChapter {
  return {
    id,
    parent_id: parentId,
    title: id,
    skip_numbering: opts.skip ?? false,
    mark_status: 'unmarked',
    sort_order: sort,
  }
}

function st(id: string, chapterId: string | null, sort: number, skip = false): EditorStep {
  return {
    id,
    chapter_id: chapterId,
    kind: 'step',
    title: id,
    content: '',
    input_schema: { type: 'COMMON' },
    attachment_marks: [],
    skip_numbering: skip,
    sort_order: sort,
  }
}

function stc(id: string, chapterId: string | null, sort: number): EditorStep {
  return { ...st(id, chapterId, sort), kind: 'content', content: '<p>x</p>' }
}

describe('recomputeCodes — §47 客户端镜像', () => {
  it('根级章节连续编号', () => {
    const { chapterCodes } = recomputeCodes([ch('a', null, 0), ch('b', null, 1)], [])
    expect(chapterCodes.get('a')).toBe('1')
    expect(chapterCodes.get('b')).toBe('2')
  })

  it('多层嵌套 N / N.M / N.M.K', () => {
    const chapters = [ch('a', null, 0), ch('a1', 'a', 0), ch('a1x', 'a1', 0)]
    const { chapterCodes } = recomputeCodes(chapters, [])
    expect(chapterCodes.get('a')).toBe('1')
    expect(chapterCodes.get('a1')).toBe('1.1')
    expect(chapterCodes.get('a1x')).toBe('1.1.1')
  })

  it('内容块步骤无号、不占步骤序号位', () => {
    const { stepCodes } = recomputeCodes([ch('a', null, 0)], [st('s1', 'a', 0), stc('c', 'a', 1), st('s2', 'a', 2)])
    expect(stepCodes.get('s1')).toBe('1.1')
    expect(stepCodes.get('c')).toBe('')
    expect(stepCodes.get('s2')).toBe('1.2')
  })

  it('skip_numbering 章节不计序号 + 子树静默', () => {
    const chapters = [
      ch('a', null, 0),
      ch('s', null, 1, { skip: true }),
      ch('sChild', 's', 0),
      ch('b', null, 2),
    ]
    const { chapterCodes } = recomputeCodes(chapters, [])
    expect(chapterCodes.get('a')).toBe('1')
    expect(chapterCodes.get('s')).toBe('')
    expect(chapterCodes.get('sChild')).toBe('') // 静默子树
    expect(chapterCodes.get('b')).toBe('2') // skip 不占位
  })

  it('步骤 = 父 chapter code + 连续序号', () => {
    const { stepCodes } = recomputeCodes(
      [ch('a', null, 0)],
      [st('s1', 'a', 0), st('s2', 'a', 1)],
    )
    expect(stepCodes.get('s1')).toBe('1.1')
    expect(stepCodes.get('s2')).toBe('1.2')
  })

  it('根级步骤为裸序号', () => {
    const { stepCodes } = recomputeCodes([], [st('s1', null, 0), st('s2', null, 1)])
    expect(stepCodes.get('s1')).toBe('1')
    expect(stepCodes.get('s2')).toBe('2')
  })

  it('skip 步骤不占序号位', () => {
    const { stepCodes } = recomputeCodes(
      [ch('a', null, 0)],
      [st('s1', 'a', 0), st('s2', 'a', 1, true), st('s3', 'a', 2)],
    )
    expect(stepCodes.get('s1')).toBe('1.1')
    expect(stepCodes.get('s2')).toBe('')
    expect(stepCodes.get('s3')).toBe('1.2')
  })

  it('按 sort_order 再 id 稳定排序', () => {
    const { chapterCodes } = recomputeCodes([ch('z', null, 0), ch('a', null, 0)], [])
    // 同 sort_order → 按 id 升序：a 在前
    expect(chapterCodes.get('a')).toBe('1')
    expect(chapterCodes.get('z')).toBe('2')
  })
})

describe('formatCode — 渲染规则', () => {
  it('L1 章节追加 .0（render-only）', () => {
    expect(formatCode({ kind: 'chapter', level: 1, code: '1', skipNumbering: false })).toBe('1.0')
  })
  it('L2+ 章节原样', () => {
    expect(formatCode({ kind: 'chapter', level: 2, code: '1.1', skipNumbering: false })).toBe('1.1')
  })
  it('跳号显示 #（优先于 .0）', () => {
    expect(formatCode({ kind: 'chapter', level: 1, code: '', skipNumbering: true })).toBe('#')
  })
  it('content / 静默 空 code → 空串', () => {
    expect(formatCode({ kind: 'content', level: 2, code: '', skipNumbering: false })).toBe('')
  })
  it('步骤不追加 .0', () => {
    expect(formatCode({ kind: 'step', level: 0, code: '1.1', skipNumbering: false })).toBe('1.1')
  })
})
