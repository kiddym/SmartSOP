import { describe, it, expect } from 'vitest'
import {
  kindOf,
  subtreeChapterIds,
  subtreeChapterHeight,
  siblingsOf,
  validDrop,
  computeDrop,
  type DndTree,
} from '@/utils/treeDnd'
import type { EditorChapter, EditorStep, FlatRow } from '@/types/node'

const ch = (
  id: string,
  parent: string | null,
  ct: 'chapter' | 'content' = 'chapter',
  sort = 0,
): EditorChapter => ({
  id,
  parent_id: parent,
  content_type: ct,
  title: id,
  rich_content: '',
  skip_numbering: false,
  mark_status: 'unmarked',
  sort_order: sort,
})

const st = (id: string, chapterId: string | null, sort = 0): EditorStep => ({
  id,
  chapter_id: chapterId,
  title: id,
  content: '',
  input_schema: { type: 'NONE' },
  expected_output: '',
  require_confirmation: false,
  attachment_marks: [],
  skip_numbering: false,
  sort_order: sort,
})

const fr = (id: string, kind: FlatRow['kind'], parent: string | null): FlatRow => ({
  id,
  kind,
  depth: 0,
  parent_id: parent,
  title: id,
  code: '',
  skip_numbering: false,
  mark_status: 'unmarked',
  form_type: null,
  require_confirmation: false,
  has_children: false,
  expanded: false,
  fallback: '',
})

function tree(chapters: EditorChapter[], steps: EditorStep[] = []): DndTree {
  const byParent = new Map<string | null, EditorChapter[]>()
  for (const c of chapters) {
    const g = byParent.get(c.parent_id) ?? []
    g.push(c)
    byParent.set(c.parent_id, g)
  }
  const levelMap = new Map<string, number>()
  const walk = (p: string | null, lv: number): void => {
    for (const c of byParent.get(p) ?? []) {
      levelMap.set(c.id, lv)
      walk(c.id, lv + 1)
    }
  }
  walk(null, 1)
  return { chapters, steps, levelMap }
}

// c1 > c2 > c3 三级链。
const chain = tree([ch('c1', null), ch('c2', 'c1'), ch('c3', 'c2')])

describe('kindOf', () => {
  it('章节 / 正文 / 步骤', () => {
    const t = tree([ch('c', null), ch('x', 'c', 'content')], [st('s', 'c')])
    expect(kindOf(t, 'c')).toBe('chapter')
    expect(kindOf(t, 'x')).toBe('content')
    expect(kindOf(t, 's')).toBe('step')
  })
})

describe('subtreeChapterIds', () => {
  it('含 root 的章节闭包', () => {
    expect([...subtreeChapterIds(chain.chapters, 'c1')].sort()).toEqual(['c1', 'c2', 'c3'])
    expect([...subtreeChapterIds(chain.chapters, 'c2')].sort()).toEqual(['c2', 'c3'])
  })
})

describe('subtreeChapterHeight', () => {
  it('仅计章节嵌套，content 为叶', () => {
    const t = tree([ch('c1', null), ch('c2', 'c1'), ch('x', 'c1', 'content')])
    expect(subtreeChapterHeight(t.chapters, 'c1')).toBe(2) // c1>c2；x 不计
    expect(subtreeChapterHeight(t.chapters, 'c2')).toBe(1)
  })
})

describe('siblingsOf', () => {
  it('按 sort_order 排序', () => {
    const t = tree([ch('c1', null), ch('b', 'c1', 'chapter', 1), ch('a', 'c1', 'chapter', 0)])
    expect(siblingsOf(t, 'c1', true).map((n) => n.id)).toEqual(['a', 'b'])
  })
})

describe('validDrop', () => {
  it('拖到自身 → false', () => {
    expect(validDrop(chain, 'c1', fr('c1', 'chapter', null), 'before')).toBe(false)
  })

  it('拖入自身子树 → false（章节循环）', () => {
    expect(validDrop(chain, 'c1', fr('c2', 'chapter', 'c1'), 'inside')).toBe(false)
  })

  it('inside 非章节目标 → false', () => {
    const t = tree([ch('c1', null), ch('x', 'c1', 'content')], [st('s', 'c1')])
    expect(validDrop(t, 's', fr('x', 'content', 'c1'), 'inside')).toBe(false)
  })

  it('章节超 3 级 → false', () => {
    const t = tree([ch('c1', null), ch('c2', 'c1'), ch('c3', 'c2'), ch('cn', null)])
    // cn（高度1）inside c3（level3）：3+1+1-1 = 4 > 3
    expect(validDrop(t, 'cn', fr('c3', 'chapter', 'c2'), 'inside')).toBe(false)
  })

  it('Q25：父级已有步骤 → 不能放章节', () => {
    const t = tree([ch('c1', null), ch('cn', null)], [st('s', 'c1')])
    expect(validDrop(t, 'cn', fr('c1', 'chapter', null), 'inside')).toBe(false)
  })

  it('合法章节拖入空章节 → true', () => {
    const t = tree([ch('c1', null), ch('cn', null)])
    expect(validDrop(t, 'cn', fr('c1', 'chapter', null), 'inside')).toBe(true)
  })

  it('步骤拖入仅含步骤的章节 → true', () => {
    const t = tree([ch('c1', null)], [st('s1', 'c1'), st('s2', null)])
    expect(validDrop(t, 's2', fr('c1', 'chapter', null), 'inside')).toBe(true)
  })
})

describe('computeDrop', () => {
  it('inside → 追加到末尾、跨父', () => {
    const t = tree([ch('c1', null), ch('a', 'c1', 'content'), ch('c2', null), ch('d', 'c2', 'content')])
    const plan = computeDrop(t, 'a', fr('c2', 'chapter', null), 'inside')
    expect(plan).toEqual({ parentId: 'c2', index: 1, currentParent: 'c1' })
  })

  it('after → 目标之后、同父重排', () => {
    const t = tree([ch('c1', null), ch('a', 'c1', 'content', 0), ch('b', 'c1', 'content', 1)])
    const plan = computeDrop(t, 'a', fr('b', 'content', 'c1'), 'after')
    expect(plan).toEqual({ parentId: 'c1', index: 1, currentParent: 'c1' })
  })

  it('步骤 currentParent 取 chapter_id', () => {
    const t = tree([ch('c1', null), ch('c2', null)], [st('s', 'c1'), st('s2', 'c2')])
    const plan = computeDrop(t, 's', fr('s2', 'step', 'c2'), 'before')
    expect(plan.currentParent).toBe('c1')
    expect(plan.parentId).toBe('c2')
  })
})
