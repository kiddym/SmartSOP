import { describe, expect, it } from 'vitest'
import {
  attachmentMarkText,
  buildModel,
  buildRevision,
  changeTypeLabel,
  coverFieldRows,
  displayCode,
  execText,
  humanSize,
  resolveFieldValue,
} from '@/components/PdfPreview/pdfModel'
import type { ProcedureDetail, ProcedureFieldView } from '@/types/procedure'
import type { PdfLayout } from '@/types/pdf'
import type { Node } from '@/types/node'

// 扁平 ProcedureNode 工厂（B5：预览改读 nodes，不再读 detail.chapters/steps）。
function node(partial: Partial<Node>): Node {
  return {
    id: 'n', procedure_id: 'p', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 0, parent_id: null, depth: 0,
    ...partial,
  }
}

// step 节点：kind='step' + input_schema 带 type；body 首块=标题，余 HTML=正文。
function stepNode(partial: Partial<Node>): Node {
  return node({
    id: 's1', kind: 'step', code: '1.1', body: '<p>步骤</p>',
    input_schema: { type: 'COMMON' }, ...partial,
  })
}

// 扁平节点列表：与旧 chapters/steps 同逻辑结构（heading 目的/操作 + 目的下内容节点 + 操作下步骤），
// 按 sort_order 升序（服务端保证）。layout 已按 node id 键化（B2b）。
function nodes(): Node[] {
  return [
    node({ id: 'c1', heading_level: 1, kind: 'node', code: '1', body: '<p>目的</p>', sort_order: 0 }),
    // 内容节点（heading_level=null, kind='node'）：正文在 body，PDF 不出编号/标题。
    node({ id: 'cc1', parent_id: 'c1', kind: 'node', body: '<p>用于规范启动</p>', sort_order: 1 }),
    node({ id: 'c2', heading_level: 1, kind: 'node', code: '2', body: '<p>操作</p>', sort_order: 2 }),
    // 步骤节点：body 首块「启动电源」=标题。
    stepNode({ id: 's1', parent_id: 'c2', code: '2.1', body: '<p>启动电源</p>', sort_order: 3 }),
  ]
}

function detail(): ProcedureDetail {
  return {
    procedure: {
      id: 'p', procedure_group_id: 'g', code: 'QC-00001', name: '启动 SOP', version: 2,
      is_current: true, status: 'PUBLISHED', folder_id: 'f', folder_full_path: '根/质检',
      description: '', risk_level: 3, quality_level: 2, level_of_use: 'continuous',
      custom_values: {}, version_update_notes: '本次新增检查', revision: 0, is_read: false,
      signoff_enabled: false,
      read_at: null, deprecated_from_folder_id: null, deprecated_at: null, archived_at: null,
      version_change_log: [
        { version: 2, change_type: 'publish', changed_at: '2026-05-20T10:00:00Z', description: '发布 v2' },
        { version: 1, change_type: 'create', changed_at: '2026-05-19T10:00:00Z', description: '创建' },
      ],
      created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-02T00:00:00Z',
    },
    // B5 后 get_detail 不再返回 chapters/steps；预览结构由 nodes() 提供。
    attachments: [],
    fields: [],
    has_source_docx: false,
  }
}

function layout(): PdfLayout {
  return {
    total_pages: 6,
    sections: {
      cover: { start_page: 1, page_count: 1 },
      toc: { start_page: 2, page_count: 1 },
      revision: { start_page: 3, page_count: 1 },
      content: { start_page: 4, page_count: 3 },
    },
    page_labels: ['', 'i', 'ii', '1', '2', '3'],
    toc_entries: [
      { chapter_id: 'c1', code: '1.0', title: '目的', level: 1, physical_page: 4, display_page: '1' },
      { chapter_id: 'c2', code: '2.0', title: '操作', level: 1, physical_page: 5, display_page: '2' },
    ],
    // 按 node id 键化（B2b：后端 pdf-layout 已用 node id）。
    chapters: { c1: 4, c2: 5 },
    steps: { s1: 5 },
    attachments_page: null,
  }
}

describe('displayCode', () => {
  it('L1 章节追加 .0（Q305）', () => expect(displayCode('1', 1, false)).toBe('1.0'))
  it('L2 不加 .0', () => expect(displayCode('1.2', 2, false)).toBe('1.2'))
  it('skip / 空 → 空串', () => {
    expect(displayCode('', 1, false)).toBe('')
    expect(displayCode('1', 1, true)).toBe('')
  })
})

describe('humanSize', () => {
  it('单位换算', () => {
    expect(humanSize(512)).toBe('512 B')
    expect(humanSize(2048)).toBe('2.00 KB')
    expect(humanSize(5 * 1024 * 1024)).toBe('5.00 MB')
  })
})

describe('changeTypeLabel', () => {
  it('翻译 + rollback 源版本', () => {
    expect(changeTypeLabel({ change_type: 'publish' })).toBe('发布')
    expect(changeTypeLabel({ change_type: 'rollback', rollback_from_version: 2 })).toContain('源 v2')
  })
})

describe('attachmentMarkText', () => {
  it('filename + kind 中文', () => {
    expect(attachmentMarkText({ filename: 'a.mp4', kind: 'video' })).toContain('a.mp4')
    expect(attachmentMarkText({ filename: 'a.mp4', kind: 'video' })).toContain('视频')
    expect(attachmentMarkText({ filename: 'd.docx', kind: 'document' })).toContain('文档')
  })
})

describe('execText', () => {
  it('CHECK / NUMBER / NONE / RADIO', () => {
    expect(execText(stepNode({ input_schema: { type: 'CHECK' } }))).toContain('通过')
    expect(execText(stepNode({ input_schema: { type: 'NUMBER', unit: 'MPa', min: 0, max: 10 } }))).toContain('0~10')
    expect(execText(stepNode({ input_schema: { type: 'NONE' } }))).toBe('')
    expect(execText(stepNode({ input_schema: { type: 'RADIO', options: ['A', 'B'] } }))).toContain('○ A')
  })
  it('警示类型（NOTE/CAUTION/WARNING）返回空串', () => {
    expect(execText(stepNode({ input_schema: { type: 'WARNING' } }))).toBe('')
    expect(execText(stepNode({ input_schema: { type: 'NOTE' } }))).toBe('')
    expect(execText(stepNode({ input_schema: { type: 'CAUTION' } }))).toBe('')
  })
})

describe('buildRevision', () => {
  it('仅里程碑 + 拼接 version_update_notes', () => {
    const rows = buildRevision(detail())
    expect(rows).toHaveLength(1) // publish（create 不入）
    expect(rows[0].changeType).toBe('发布')
    expect(rows[0].desc).toContain('本次新增检查')
  })
})

describe('buildModel', () => {
  it('TOC 取 layout、正文按页号分组（块键用 node id）', () => {
    const m = buildModel(detail(), nodes(), layout())
    expect(m.toc).toHaveLength(2)
    expect(m.contentPages).toHaveLength(3) // content 区段 3 页
    // c1 在第 4 页（content 第 1 页）
    const p4 = m.contentPages.find((p) => p.page === 4)!
    expect(p4.blocks.some((b) => b.kind === 'chapter' && b.key === 'ch-c1' && b.code === '1.0')).toBe(true)
    // content 节点继承 c1 页，键 c-<nodeId>
    expect(p4.blocks.some((b) => b.kind === 'content' && b.key === 'c-cc1')).toBe(true)
    // c2 + step 在第 5 页
    const p5 = m.contentPages.find((p) => p.page === 5)!
    expect(p5.blocks.some((b) => b.kind === 'chapter' && b.key === 'ch-c2' && b.code === '2.0')).toBe(true)
    const stepBlock = p5.blocks.find((b) => b.kind === 'step' && b.key === 'st-s1')!
    expect(stepBlock).toBeTruthy()
    // body 首块切为标题，code 取 node.code
    expect(stepBlock.title).toBe('启动电源')
    expect(stepBlock.code).toBe('2.1')
  })

  it('正文块按文档序（章节 → 其内容/步骤）', () => {
    const m = buildModel(detail(), nodes(), layout())
    const keys = m.contentPages.flatMap((p) => p.blocks.map((b) => b.key))
    expect(keys).toEqual(['ch-c1', 'c-cc1', 'ch-c2', 'st-s1'])
  })

  it('页 label 来自 layout.page_labels', () => {
    const m = buildModel(detail(), nodes(), layout())
    expect(m.contentPages[0].label).toBe('1')
  })

  it('exposes signoffEnabled from procedure', () => {
    const d = detail()
    d.procedure.signoff_enabled = true
    const model = buildModel(d, nodes(), layout())
    expect(model.signoffEnabled).toBe(true)
  })
})

function field(partial: Partial<ProcedureFieldView>): ProcedureFieldView {
  return {
    id: 'f', name: '字段', key: 'k', field_type: 'text', required: false,
    options: [], sort_order: 0, show_on_cover: false, ...partial,
  }
}

describe('resolveFieldValue', () => {
  it('select 解析为 label', () => {
    const f = field({ field_type: 'select', options: [{ value: 'a', label: '甲' }] })
    expect(resolveFieldValue(f, 'a')).toBe('甲')
    expect(resolveFieldValue(f, 'x')).toBe('x') // 无映射回退原值
  })
  it('multi_select 逗号拼接 label', () => {
    const f = field({ field_type: 'multi_select', options: [{ value: 'a', label: '甲' }, { value: 'b', label: '乙' }] })
    expect(resolveFieldValue(f, ['a', 'b'])).toBe('甲、乙')
  })
  it('空值 → 空串', () => {
    expect(resolveFieldValue(field({}), '')).toBe('')
    expect(resolveFieldValue(field({ field_type: 'multi_select' }), [])).toBe('')
  })
})

describe('coverFieldRows', () => {
  it('仅 show_on_cover 且有值，按 sort_order 排序', () => {
    const d = detail()
    d.procedure.custom_values = { a: 'a', b: 'X', c: '' }
    d.fields = [
      field({ key: 'a', name: '类别', field_type: 'select', options: [{ value: 'a', label: '甲' }], show_on_cover: true, sort_order: 1 }),
      field({ key: 'b', name: '编号', show_on_cover: true, sort_order: 0 }),
      field({ key: 'c', name: '隐藏空值', show_on_cover: true, sort_order: 2 }), // 空值剔除
      field({ key: 'd', name: '不上封面', show_on_cover: false, sort_order: 3 }),
    ]
    const rows = coverFieldRows(d)
    expect(rows).toEqual([
      { name: '编号', value: 'X' },
      { name: '类别', value: '甲' },
    ])
  })
})

describe('buildModel 附件区段', () => {
  it('无用户附件章节 → 虚拟章节标题 {n}.0', () => {
    const d = detail()
    d.attachments = [
      { id: 'a1', file_name: '图.pdf', size_bytes: 2048, mime_type: 'application/pdf', created_at: '2026-05-01T00:00:00Z', description: '' },
    ]
    const l = layout()
    l.attachments_page = 6
    l.page_labels = ['', 'i', 'ii', '1', '2', '3']
    const m = buildModel(d, nodes(), l)
    expect(m.attachments).toHaveLength(1)
    expect(m.attachments[0].fileName).toBe('图.pdf')
    expect(m.attachmentChapterTitle).toBe('3.0 附件 / Attachments') // 末顶层章节 L1=2 → 3
  })
  it('用户自建「附件」章节 → 标题为 null（不重复）', () => {
    const d = detail()
    const ns = nodes()
    // 顶层 heading 节点 body 首块文本=「附件」→ 视为用户自建附件章节。
    ns.push(node({ id: 'c3', heading_level: 1, kind: 'node', code: '3', body: '<p>附件</p>', sort_order: 4 }))
    d.attachments = [
      { id: 'a1', file_name: '图.pdf', size_bytes: 2048, mime_type: 'application/pdf', created_at: '2026-05-01T00:00:00Z', description: '' },
    ]
    const m = buildModel(d, ns, layout())
    expect(m.attachmentChapterTitle).toBeNull()
  })
})
