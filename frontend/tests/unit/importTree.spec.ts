import { describe, expect, it } from 'vitest'
import {
  buildTreeFromRoles,
  buildWizardTree,
  clearReview,
  computeChapterNumbers,
  computeLevelMap,
  computeMarkIndents,
  countReview,
  defaultRoleOf,
  deleteNode,
  findNode,
  flattenForMarking,
  moveNode,
  toImportNodes,
  updateNode,
} from '@/utils/importTree'
import type { LayerRole } from '@/utils/importTree'
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

function sampleTree() {
  return buildWizardTree([
    pnode({
      id: 'a',
      title: '目的',
      children: [pnode({ id: 'a1', title: '正文', content_type: 'content' })],
    }),
    pnode({ id: 'b', title: '范围', mark_status: 'review', confidence_tier: 'low' }),
    pnode({ id: 'c', title: '职责' }),
  ])
}

describe('importTree 纯函数', () => {
  it('buildWizardTree 保留层级与编辑相关字段，丢弃派生字段', () => {
    const tree = sampleTree()
    expect(tree).toHaveLength(3)
    expect(tree[0].children[0].content_type).toBe('content')
    expect(tree[1].mark_status).toBe('review')
    expect(tree[1].confidence_tier).toBe('low')
    // 不应携带派生字段
    expect('order' in tree[0]).toBe(false)
    expect('level' in tree[0]).toBe(false)
  })

  it('findNode 深度查找', () => {
    const tree = sampleTree()
    expect(findNode(tree, 'a1')?.title).toBe('正文')
    expect(findNode(tree, 'zzz')).toBeNull()
  })

  it('updateNode 不可变更新指定节点', () => {
    const tree = sampleTree()
    const next = updateNode(tree, 'a', { title: '总则', skip_numbering: true })
    expect(findNode(next, 'a')?.title).toBe('总则')
    expect(findNode(next, 'a')?.skip_numbering).toBe(true)
    // 原树不变
    expect(findNode(tree, 'a')?.title).toBe('目的')
  })

  it('deleteNode 递归删除整棵子树', () => {
    const tree = sampleTree()
    const next = deleteNode(tree, 'a')
    expect(next).toHaveLength(2)
    expect(findNode(next, 'a1')).toBeNull()
  })

  it('moveNode 同级上移 / 下移，边界 no-op', () => {
    const tree = sampleTree()
    const up = moveNode(tree, 'c', -1)
    expect(up.map((n) => n.id)).toEqual(['a', 'c', 'b'])
    const down = moveNode(tree, 'a', 1)
    expect(down.map((n) => n.id)).toEqual(['b', 'a', 'c'])
    // 顶部上移 no-op
    expect(moveNode(tree, 'a', -1).map((n) => n.id)).toEqual(['a', 'b', 'c'])
    // 底部下移 no-op
    expect(moveNode(tree, 'c', 1).map((n) => n.id)).toEqual(['a', 'b', 'c'])
  })

  it('countReview 统计 review 节点', () => {
    expect(countReview(sampleTree())).toBe(1)
  })

  it('clearReview 把 review→unmarked（不动其他态）', () => {
    const cleared = clearReview(sampleTree())
    expect(countReview(cleared)).toBe(0)
    expect(findNode(cleared, 'b')?.mark_status).toBe('unmarked')
  })

  it('toImportNodes 压成导入形态并清 review', () => {
    const out = toImportNodes(sampleTree())
    expect(out[0]).toEqual({
      title: '目的',
      content_type: 'chapter',
      rich_content: '',
      skip_numbering: false,
      mark_status: 'unmarked',
      children: [
        {
          title: '正文',
          content_type: 'content',
          rich_content: '',
          skip_numbering: false,
          mark_status: 'unmarked',
          children: [],
        },
      ],
    })
    // review 节点已清
    expect(out[1].mark_status).toBe('unmarked')
    // 无 id / confidence_tier 等向导内部字段
    expect('id' in out[0]).toBe(false)
    expect('confidence_tier' in out[0]).toBe(false)
  })
})

describe('computeChapterNumbers', () => {
  it('flat list: assigns sequential integers starting at 1', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', title: 'A' }),
      pnode({ id: 'b', title: 'B' }),
      pnode({ id: 'c', title: 'C' }),
    ])
    expect(computeChapterNumbers(tree)).toEqual({ a: '1', b: '2', c: '3' })
  })

  it('nested children get dotted prefix from parent', () => {
    const tree = buildWizardTree([
      pnode({
        id: 'a',
        title: 'A',
        children: [
          pnode({ id: 'a1', title: 'A1' }),
          pnode({ id: 'a2', title: 'A2' }),
        ],
      }),
      pnode({
        id: 'b',
        title: 'B',
        children: [
          pnode({
            id: 'b1',
            title: 'B1',
            children: [pnode({ id: 'b1a', title: 'B1A' })],
          }),
        ],
      }),
    ])
    const nums = computeChapterNumbers(tree)
    expect(nums.a).toBe('1')
    expect(nums.a1).toBe('1.1')
    expect(nums.a2).toBe('1.2')
    expect(nums.b).toBe('2')
    expect(nums.b1).toBe('2.1')
    expect(nums.b1a).toBe('2.1.1')
  })

  it('skip_numbering=true: excluded from map and does not consume sequence', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', title: 'A' }),
      pnode({ id: 's', title: 'Skip', skip_numbering: true }),
      pnode({ id: 'b', title: 'B' }),
    ])
    const nums = computeChapterNumbers(tree)
    expect(nums.a).toBe('1')
    expect('s' in nums).toBe(false)
    expect(nums.b).toBe('2') // sequence is 2, not 3
  })

  it('content nodes are not numbered', () => {
    const tree = buildWizardTree([
      pnode({
        id: 'a',
        title: 'A',
        children: [pnode({ id: 'c', title: 'Content', content_type: 'content' })],
      }),
    ])
    const nums = computeChapterNumbers(tree)
    expect(nums.a).toBe('1')
    expect('c' in nums).toBe(false)
  })

  it('empty tree returns empty object', () => {
    expect(computeChapterNumbers([])).toEqual({})
  })
})

describe('defaultRoleOf', () => {
  it('content→content；章节按深度（>3 夹紧 3）', () => {
    const c = buildWizardTree([pnode({ id: 'c', content_type: 'content' })])[0]
    const h = buildWizardTree([pnode({ id: 'h' })])[0]
    expect(defaultRoleOf(c, 1)).toBe('content')
    expect(defaultRoleOf(h, 1)).toBe('chapter_1')
    expect(defaultRoleOf(h, 2)).toBe('chapter_2')
    expect(defaultRoleOf(h, 3)).toBe('chapter_3')
    expect(defaultRoleOf(h, 5)).toBe('chapter_3')
  })
})

describe('flattenForMarking', () => {
  it('按文档前序拍平 + 默认级别映射 + 正文摘要', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', title: '目的', children: [
        pnode({ id: 'a1', title: '范围' }),
        pnode({ id: 'a2', content_type: 'content', rich_content: '<p>正文内容</p>' }),
      ] }),
      pnode({ id: 'b', title: '职责' }),
    ])
    const rows = flattenForMarking(tree)
    expect(rows.map((r) => r.id)).toEqual(['a', 'a1', 'a2', 'b'])
    expect(rows.map((r) => r.defaultRole)).toEqual(['chapter_1', 'chapter_2', 'content', 'chapter_1'])
    expect(rows[2].label).toBe('正文内容')
    expect(rows[0].label).toBe('目的')
  })

  it('深度>3 的章节默认夹紧为 chapter_3', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', children: [pnode({ id: 'b', children: [
        pnode({ id: 'c', children: [pnode({ id: 'd' })] }),
      ] })] }),
    ])
    expect(flattenForMarking(tree).find((r) => r.id === 'd')?.defaultRole).toBe('chapter_3')
  })

  it('空标题章节 label 回落（无标题）', () => {
    const tree = buildWizardTree([pnode({ id: 'a', title: '' })])
    expect(flattenForMarking(tree)[0].label).toBe('（无标题）')
  })

  it('空正文节点 label 为空字符串（仅章节才回落"无标题"）', () => {
    const tree = buildWizardTree([pnode({ id: 'x', content_type: 'content', rich_content: '' })])
    expect(flattenForMarking(tree)[0].label).toBe('')
  })
})

function rmap(obj: Record<string, LayerRole>): Map<string, LayerRole> {
  return new Map(Object.entries(obj) as [string, LayerRole][])
}

describe('buildTreeFromRoles', () => {
  it('默认级别 round-trip：结构不变', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', children: [pnode({ id: 'a1', content_type: 'content', rich_content: '<p>x</p>' })] }),
      pnode({ id: 'b' }),
    ])
    const m = new Map(flattenForMarking(tree).map((r) => [r.id, r.defaultRole]))
    const out = buildTreeFromRoles(tree, m)
    expect(out.map((n) => n.id)).toEqual(['a', 'b'])
    expect(out[0].children.map((n) => n.id)).toEqual(['a1'])
    expect(out[0].children[0].content_type).toBe('content')
  })

  it('正文挂到最近最深章节；开头即正文落根', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a' }),
      pnode({ id: 'x', content_type: 'content', rich_content: '<p>x</p>' }),
    ])
    const out = buildTreeFromRoles(tree, rmap({ a: 'chapter_1', x: 'content' }))
    expect(out.map((n) => n.id)).toEqual(['a'])
    expect(out[0].children.map((n) => n.id)).toEqual(['x'])

    const tree2 = buildWizardTree([pnode({ id: 'x', content_type: 'content', rich_content: '<p>x</p>' })])
    const out2 = buildTreeFromRoles(tree2, rmap({ x: 'content' }))
    expect(out2.map((n) => n.id)).toEqual(['x'])
    expect(out2[0].content_type).toBe('content')
  })

  it('层级跳跃夹紧：chapter_2 无一级父→根级；chapter_3 无二级父→退挂一级', () => {
    const tree = buildWizardTree([pnode({ id: 'a' }), pnode({ id: 'b' })])
    const out = buildTreeFromRoles(tree, rmap({ a: 'chapter_2', b: 'chapter_3' }))
    expect(out.map((n) => n.id)).toEqual(['a'])
    expect(out[0].children.map((n) => n.id)).toEqual(['b'])
    expect(computeLevelMap(out).get('a')).toBe(1)
    expect(computeLevelMap(out).get('b')).toBe(2)
  })

  it('顺序无关：map 写入顺序不影响结果', () => {
    const tree = buildWizardTree([pnode({ id: 'A' }), pnode({ id: 'B' }), pnode({ id: 'C' })])
    const out1 = buildTreeFromRoles(tree, new Map<string, LayerRole>([['A', 'chapter_1'], ['B', 'chapter_2'], ['C', 'chapter_2']]))
    const out2 = buildTreeFromRoles(tree, new Map<string, LayerRole>([['C', 'chapter_2'], ['A', 'chapter_1'], ['B', 'chapter_2']]))
    expect(out2).toEqual(out1)
    expect(out1[0].children.map((n) => n.id)).toEqual(['B', 'C'])
  })

  it('内容升级为章节：文本作标题、清空正文、参与编号', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a' }),
      pnode({ id: 'x', content_type: 'content', title: '', rich_content: '<p>操作步骤</p>' }),
    ])
    const x = buildTreeFromRoles(tree, rmap({ a: 'chapter_1', x: 'chapter_2' }))[0].children[0]
    expect(x.id).toBe('x')
    expect(x.content_type).toBe('chapter')
    expect(x.title).toBe('操作步骤')
    expect(x.rich_content).toBe('')
    expect(x.skip_numbering).toBe(false)
  })

  it('章节降级为正文：标题回填正文、skip_numbering=true', () => {
    const tree = buildWizardTree([pnode({ id: 'a', title: '操作' })])
    const out = buildTreeFromRoles(tree, rmap({ a: 'content' }))
    expect(out[0].content_type).toBe('content')
    expect(out[0].rich_content).toContain('操作')
    expect(out[0].skip_numbering).toBe(true)
  })

  it('全部设为正文：均落根且为 content', () => {
    const tree = buildWizardTree([pnode({ id: 'a' }), pnode({ id: 'b' })])
    const out = buildTreeFromRoles(tree, rmap({ a: 'content', b: 'content' }))
    expect(out.map((n) => n.id)).toEqual(['a', 'b'])
    expect(out.every((n) => n.content_type === 'content')).toBe(true)
  })

  it('chapter_3 直接挂一级（无二级父，跳过二级层）', () => {
    const tree = buildWizardTree([pnode({ id: 'a' }), pnode({ id: 'b' })])
    const out = buildTreeFromRoles(tree, rmap({ a: 'chapter_1', b: 'chapter_3' }))
    expect(out.map((n) => n.id)).toEqual(['a'])
    expect(out[0].children.map((n) => n.id)).toEqual(['b'])
    expect(computeLevelMap(out).get('b')).toBe(2)
  })

  it('roleMap 缺某 id → 该节点回落解析默认级别（defaultRoleOf）', () => {
    const tree = buildWizardTree([
      pnode({ id: 'a', children: [pnode({ id: 'a1' })] }),
    ])
    // 只显式给 a；a1 缺失 → 回落 chapter_2（其原始深度）
    const out = buildTreeFromRoles(tree, rmap({ a: 'chapter_1' }))
    expect(out.map((n) => n.id)).toEqual(['a'])
    expect(out[0].children.map((n) => n.id)).toEqual(['a1'])
    expect(computeLevelMap(out).get('a1')).toBe(2)
  })
})

describe('computeMarkIndents', () => {
  it('章节缩进=level-1；正文比当前标题深一级', () => {
    const rows = [
      { id: 'a', label: 'A', defaultRole: 'chapter_1' as LayerRole },
      { id: 'b', label: 'B', defaultRole: 'chapter_2' as LayerRole },
      { id: 'x', label: 'X', defaultRole: 'content' as LayerRole },
      { id: 'c', label: 'C', defaultRole: 'chapter_1' as LayerRole },
    ]
    const m = computeMarkIndents(rows, new Map(rows.map((r) => [r.id, r.defaultRole])))
    expect(m.get('a')).toBe(0)
    expect(m.get('b')).toBe(1)
    expect(m.get('x')).toBe(2)
    expect(m.get('c')).toBe(0)
  })

  it('开头即正文（无标题）缩进 0', () => {
    const m = computeMarkIndents(
      [{ id: 'x', label: 'X', defaultRole: 'content' as LayerRole }],
      new Map([['x', 'content' as LayerRole]]),
    )
    expect(m.get('x')).toBe(0)
  })

  it('roleMap 覆盖默认：b 改正文后挂在一级标题 a 下（缩进 1）', () => {
    const rows = [
      { id: 'a', label: 'A', defaultRole: 'chapter_1' as LayerRole },
      { id: 'b', label: 'B', defaultRole: 'chapter_2' as LayerRole },
    ]
    const m = computeMarkIndents(rows, new Map<string, LayerRole>([['a', 'chapter_1'], ['b', 'content']]))
    expect(m.get('b')).toBe(1)
  })

  it('正文在三级标题下缩进 3', () => {
    const rows = [
      { id: 'h3', label: 'H3', defaultRole: 'chapter_3' as LayerRole },
      { id: 'c', label: 'C', defaultRole: 'content' as LayerRole },
    ]
    const m = computeMarkIndents(rows, new Map(rows.map((r) => [r.id, r.defaultRole])))
    expect(m.get('h3')).toBe(2)
    expect(m.get('c')).toBe(3)
  })

  it('chapter_2 无前置一级仍缩进 1（所见即所选，不夹紧）', () => {
    const rows = [{ id: 'b', label: 'B', defaultRole: 'chapter_2' as LayerRole }]
    const m = computeMarkIndents(rows, new Map([['b', 'chapter_2' as LayerRole]]))
    expect(m.get('b')).toBe(1)
  })
})
