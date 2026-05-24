import { describe, expect, it } from 'vitest'
import {
  addChildNode,
  addSiblingNode,
  buildWizardTree,
  computeLevelMap,
  extractIgnored,
  findParent,
  restoreFromIgnored,
  setMarkStatus,
} from '@/utils/importTree'
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

  it('addSiblingNode 不存在的 id 返回原树', () => {
    const tree = sample()
    const next = addSiblingNode(tree, 'zzz', 'chapter')
    expect(next).toEqual(tree)
  })

  it('extractIgnored 同时含父子 id：子随父移除（不重复）', () => {
    const tree = sample()
    // 'a' contains 'a1' — if both in ids, a1 is swallowed inside removed 'a'
    const [next, removed] = extractIgnored(tree, ['a', 'a1'])
    expect(removed).toHaveLength(1) // only 'a' is top-level removed; a1 is inside it
    expect(removed[0].id).toBe('a')
    expect(next.map((n) => n.id)).toEqual(['b'])
  })
})
