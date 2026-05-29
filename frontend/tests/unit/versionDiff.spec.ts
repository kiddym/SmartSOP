import { describe, it, expect } from 'vitest'
import { nodeSignature, changedFields, diffVersions } from '@/components/version/versionDiff'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

describe('nodeSignature', () => {
  it('uses code when present, else first-line title', () => {
    expect(nodeSignature(n({ code: '3.1', body: '<p>职责</p>' }))).toBe('3.1')
    expect(nodeSignature(n({ code: '', body: '<p>正文内容</p>' }))).toBe('正文内容')
  })
})

describe('changedFields', () => {
  it('detects body / level / kind / form changes; none when identical', () => {
    expect(changedFields(n({ body: '<p>a</p>' }), n({ body: '<p>b</p>' }))).toEqual(['正文'])
    expect(changedFields(n({ heading_level: 1 }), n({ heading_level: 2 }))).toEqual(['层级'])
    expect(changedFields(n({ kind: 'node' }), n({ kind: 'step' }))).toContain('类型')
    expect(changedFields(n({ input_schema: { type: 'NOTE' } }), n({ input_schema: { type: 'CHECK' } }))).toContain('执行表单')
    expect(changedFields(n({ body: '<p>a</p>' }), n({ body: '<p>a</p>' }))).toEqual([])
  })
})

describe('diffVersions', () => {
  it('identical trees → all unchanged', () => {
    const t = [n({ code: '1', body: '<p>目的</p>' }), n({ code: '', body: '<p>正文</p>', sort_order: 1 })]
    const rows = diffVersions(t, t.map((x) => ({ ...x })))
    expect(rows.map((r) => r.status)).toEqual(['unchanged', 'unchanged'])
  })
  it('added node only in new', () => {
    const old = [n({ code: '1', body: '<p>A</p>' })]
    const neu = [n({ code: '1', body: '<p>A</p>' }), n({ code: '2', body: '<p>B</p>', sort_order: 1 })]
    const rows = diffVersions(old, neu)
    expect(rows.map((r) => r.status)).toEqual(['unchanged', 'added'])
    expect(rows[1].new?.code).toBe('2')
  })
  it('removed node only in old', () => {
    const old = [n({ code: '1', body: '<p>A</p>' }), n({ code: '2', body: '<p>B</p>', sort_order: 1 })]
    const neu = [n({ code: '1', body: '<p>A</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows.map((r) => r.status)).toEqual(['unchanged', 'removed'])
    expect(rows[1].old?.code).toBe('2')
  })
  it('same signature, different body → modified with changedFields', () => {
    const old = [n({ code: '1', body: '<p>目的</p>' })]
    const neu = [n({ code: '1', body: '<p>目的（修订）多一句</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows).toHaveLength(1)
    expect(rows[0].status).toBe('modified')
    expect(rows[0].changedFields).toEqual(['正文'])
  })
  it('duplicate-title content matched positionally', () => {
    const mk = () => [n({ code: '', body: '<p>未命名</p>' }), n({ code: '', body: '<p>未命名</p>', sort_order: 1 })]
    expect(diffVersions(mk(), mk()).map((r) => r.status)).toEqual(['unchanged', 'unchanged'])
  })
  it('empty old → all added; empty new → all removed', () => {
    expect(diffVersions([], [n({ code: '1' })]).map((r) => r.status)).toEqual(['added'])
    expect(diffVersions([n({ code: '1' })], []).map((r) => r.status)).toEqual(['removed'])
  })
  it('rename: a title change (different signature) → one modified row, not remove+add', () => {
    const old = [n({ id: 'o', code: '', body: '<p>目的</p><p>本程序适用于公司股东</p>' })]
    const neu = [n({ id: 'nn', code: '', body: '<p>宗旨</p><p>本程序适用于公司股东</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows).toHaveLength(1)
    expect(rows[0].status).toBe('modified')
    expect(rows[0].changedFields).toEqual(['正文'])
    expect(rows[0].old?.id).toBe('o')
    expect(rows[0].new?.id).toBe('nn')
  })
  it('pure renumber (identical body, code differs) stays remove+add', () => {
    const old = [n({ id: 'o', code: '3.1', body: '<p>多少分</p>' })]
    const neu = [n({ id: 'nn', code: '4.1', body: '<p>多少分</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows.map((r) => r.status).sort()).toEqual(['added', 'removed'])
  })
  it('dissimilar add+remove (changed fields but low overlap) stays separate', () => {
    const old = [n({ id: 'o', code: '', body: '<p>完全旧</p>' })]
    const neu = [n({ id: 'nn', code: '', body: '<p>毫不相干新内容</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows.map((r) => r.status).sort()).toEqual(['added', 'removed'])
  })
})
