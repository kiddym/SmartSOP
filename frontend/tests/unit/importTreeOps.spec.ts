import { describe, expect, it } from 'vitest'
import {
  addChildNode,
  addSiblingNode,
  computeLevelMap,
  demoteNode,
  extractIgnored,
  findParent,
  promoteNode,
  restoreFromIgnored,
  setMarkStatus,
} from '@/utils/importTree'
import { buildWizardTree } from '@/utils/importTree'
import type { ParsedNode } from '@/types/parse'

function pnode(partial: Partial<ParsedNode> & { id: string }): ParsedNode {
  return {
    id: partial.id,
    title: partial.title ?? '',
    level: partial.level ?? 1,
    order: partial.order ?? 0,
    parent_id: partial.parent_id ?? null,
    content_type: partial.content_type ?? 'chapter',
    rich_content: partial.rich_content ?? '',
    skip_numbering: partial.skip_numbering ?? false,
    confidence: partial.confidence ?? 1,
    confidence_tier: partial.confidence_tier ?? 'high',
    mark_status: partial.mark_status ?? 'unmarked',
    heading_source: partial.heading_source ?? null,
    children: partial.children ?? [],
  }
}

function sample() {
  return buildWizardTree([
    pnode({
      id: 'a',
      children: [
        pnode({ id: 'a1', children: [pnode({ id: 'a1a' })] }),
        pnode({ id: 'a2' }),
      ],
    }),
    pnode({ id: 'b' }),
  ])
}

describe('importTree 新增操作', () => {
  it('findParent 返回父节点；根节点返回 null', () => {
    const tree = sample()
    expect(findParent(tree, 'a1a')?.id).toBe('a1')
    expect(findParent(tree, 'a1')?.id).toBe('a')
    expect(findParent(tree, 'a')).toBeNull()
    expect(findParent(tree, 'zzz')).toBeNull()
  })

  it('computeLevelMap 计算每个节点深度，根=1', () => {
    const tree = sample()
    const m = computeLevelMap(tree)
    expect(m.get('a')).toBe(1)
    expect(m.get('a1')).toBe(2)
    expect(m.get('a1a')).toBe(3)
    expect(m.get('b')).toBe(1)
  })

  it('addChildNode 在指定 parent 末尾追加 chapter 节点', () => {
    const tree = sample()
    const next = addChildNode(tree, 'a1', 'chapter')
    const a1 = next[0].children[0]
    expect(a1.children).toHaveLength(2)
    const added = a1.children[1]
    expect(added.content_type).toBe('chapter')
    expect(added.title).toBe('')
    expect(added.id).toMatch(/^new-/)
  })

  it('addChildNode 支持 content 子节点', () => {
    const tree = sample()
    const next = addChildNode(tree, 'a', 'content')
    const added = next[0].children[2]
    expect(added.content_type).toBe('content')
    expect(added.skip_numbering).toBe(true)
  })

  it('addChildNode parentId=null 时在根末尾追加', () => {
    const tree = sample()
    const next = addChildNode(tree, null, 'chapter')
    expect(next).toHaveLength(3)
    expect(next[2].title).toBe('')
  })

  it('addSiblingNode 在指定节点之后插入同级', () => {
    const tree = sample()
    const next = addSiblingNode(tree, 'a1', 'chapter')
    expect(next[0].children).toHaveLength(3)
    expect(next[0].children[1].id).toMatch(/^new-/)
    expect(next[0].children[2].id).toBe('a2')
  })

  it('promoteNode 把子节点提升到父的同级（紧跟父之后）', () => {
    const tree = sample()
    // a1 提升 → a 之后变成 a, a1, b（a1a 仍是 a1 的子）
    const next = promoteNode(tree, 'a1')
    expect(next.map((n) => n.id)).toEqual(['a', 'a1', 'b'])
    expect(next[0].children.map((c) => c.id)).toEqual(['a2'])
    expect(next[1].children.map((c) => c.id)).toEqual(['a1a'])
  })

  it('promoteNode 根节点 no-op', () => {
    const tree = sample()
    const next = promoteNode(tree, 'a')
    expect(next).toEqual(tree)
  })

  it('demoteNode 把节点降为前一个同级的最后一个子', () => {
    const tree = sample()
    // a2 降级 → 变成 a1 的子（在 a1a 后）
    const next = demoteNode(tree, 'a2')
    expect(next[0].children.map((c) => c.id)).toEqual(['a1'])
    expect(next[0].children[0].children.map((c) => c.id)).toEqual(['a1a', 'a2'])
  })

  it('demoteNode 同级首位 no-op（无前一个同级）', () => {
    const tree = sample()
    const next = demoteNode(tree, 'a1')
    expect(next).toEqual(tree)
  })

  it('setMarkStatus 设置单节点 mark_status', () => {
    const tree = sample()
    const next = setMarkStatus(tree, 'a1', 'step')
    expect(next[0].children[0].mark_status).toBe('step')
    expect(next[0].mark_status).toBe('unmarked')
  })

  it('setMarkStatus 批量设置多节点', () => {
    const tree = sample()
    const next = setMarkStatus(tree, ['a1', 'b'], 'content')
    expect(next[0].children[0].mark_status).toBe('content')
    expect(next[1].mark_status).toBe('content')
  })

  it('extractIgnored 从树中移除节点并返回 [新树, 被移除节点]', () => {
    const tree = sample()
    const [next, removed] = extractIgnored(tree, ['a1'])
    expect(removed).toHaveLength(1)
    expect(removed[0].id).toBe('a1')
    expect(next[0].children.map((c) => c.id)).toEqual(['a2'])
  })

  it('restoreFromIgnored 把节点追加回根末尾', () => {
    const tree = sample()
    const [stripped, removed] = extractIgnored(tree, ['a1'])
    const restored = restoreFromIgnored(stripped, removed)
    expect(restored.map((n) => n.id)).toEqual(['a', 'b', 'a1'])
  })
})
