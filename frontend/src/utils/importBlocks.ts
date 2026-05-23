import type { ImportNode, ParsedImportBlock } from '@/types/parse'
import type { MarkStatus } from '@/types/node'

export type MarkRole = 'content' | 'chapter_1' | 'chapter_2' | 'chapter_3' | 'ignored'

export interface MarkedImportBlock extends ParsedImportBlock {
  assigned_role: MarkRole
}

export interface MarkValidationIssue {
  block_id: string
  level: 'error' | 'warning'
  message: string
}

function suggestedRole(block: ParsedImportBlock): MarkRole {
  if (block.suggested_type !== 'chapter') return 'content'
  if (block.suggested_level === 1) return 'chapter_1'
  if (block.suggested_level === 2) return 'chapter_2'
  if (block.suggested_level === 3) return 'chapter_3'
  return 'content'
}

function roleLevel(role: MarkRole): 1 | 2 | 3 | null {
  if (role === 'chapter_1') return 1
  if (role === 'chapter_2') return 2
  if (role === 'chapter_3') return 3
  return null
}

export function buildMarkedBlocks(blocks: ParsedImportBlock[]): MarkedImportBlock[] {
  return [...blocks]
    .sort((a, b) => a.source_index - b.source_index)
    .map((b) => ({ ...b, assigned_role: suggestedRole(b) }))
}

export function applyBatchMark(
  blocks: MarkedImportBlock[],
  ids: string[],
  role: MarkRole,
): MarkedImportBlock[] {
  const selected = new Set(ids)
  return blocks.map((b) => (selected.has(b.id) ? { ...b, assigned_role: role } : { ...b }))
}

export function clearBatchMark(blocks: MarkedImportBlock[], ids: string[]): MarkedImportBlock[] {
  const selected = new Set(ids)
  return blocks.map((b) => (selected.has(b.id) ? { ...b, assigned_role: 'content' } : { ...b }))
}

function contentNode(block: MarkedImportBlock): ImportNode {
  return {
    id: crypto.randomUUID(),
    title: '',
    content_type: 'content',
    rich_content: block.rich_content,
    skip_numbering: true,
    mark_status: block.mark_status === 'review' ? 'unmarked' : (block.mark_status as MarkStatus),
    children: [],
  }
}

function chapterNode(block: MarkedImportBlock): ImportNode {
  return {
    id: crypto.randomUUID(),
    title: block.clean_text.trim() || block.display_text.trim(),
    content_type: 'chapter',
    rich_content: '',
    skip_numbering: false,
    mark_status: block.mark_status === 'review' ? 'unmarked' : (block.mark_status as MarkStatus),
    children: [],
  }
}

export function rebuildTreeFromMarks(blocks: MarkedImportBlock[]): ImportNode[] {
  const roots: ImportNode[] = []
  let currentL1: ImportNode | null = null
  let currentL2: ImportNode | null = null
  let currentL3: ImportNode | null = null

  for (const block of [...blocks].sort((a, b) => a.source_index - b.source_index)) {
    if (block.assigned_role === 'ignored') continue
    const level = roleLevel(block.assigned_role)
    if (level === 1) {
      const node = chapterNode(block)
      roots.push(node)
      currentL1 = node
      currentL2 = null
      currentL3 = null
      continue
    }
    if (level === 2) {
      if (!currentL1) continue
      const node = chapterNode(block)
      currentL1.children.push(node)
      currentL2 = node
      currentL3 = null
      continue
    }
    if (level === 3) {
      if (!currentL2) continue
      const node = chapterNode(block)
      currentL2.children.push(node)
      currentL3 = node
      continue
    }
    const parent = currentL3 ?? currentL2 ?? currentL1
    if (parent) parent.children.push(contentNode(block))
  }

  return roots
}

export function validateMarkedBlocks(blocks: MarkedImportBlock[]): MarkValidationIssue[] {
  const issues: MarkValidationIssue[] = []
  let seenL1 = false
  let seenL2 = false
  for (const block of [...blocks].sort((a, b) => a.source_index - b.source_index)) {
    if (block.assigned_role === 'ignored') continue
    if (block.assigned_role === 'chapter_1') {
      seenL1 = true
      seenL2 = false
      if (!(block.clean_text.trim() || block.display_text.trim())) {
        issues.push({ block_id: block.id, level: 'error', message: '章节标题不能为空' })
      }
      continue
    }
    if (block.assigned_role === 'chapter_2') {
      if (!seenL1) {
        issues.push({ block_id: block.id, level: 'error', message: '二级章节前缺少一级章节' })
      }
      seenL2 = true
      if (!(block.clean_text.trim() || block.display_text.trim())) {
        issues.push({ block_id: block.id, level: 'error', message: '章节标题不能为空' })
      }
      continue
    }
    if (block.assigned_role === 'chapter_3') {
      if (!seenL2) {
        issues.push({ block_id: block.id, level: 'error', message: '三级章节前缺少二级章节' })
      }
      if (!(block.clean_text.trim() || block.display_text.trim())) {
        issues.push({ block_id: block.id, level: 'error', message: '章节标题不能为空' })
      }
      continue
    }
    if (!seenL1 && block.assigned_role === 'content' && block.rich_content.trim()) {
      issues.push({ block_id: block.id, level: 'warning', message: '正文位于第一个一级章节之前' })
    }
  }
  return issues
}

export function toImportNodesFromBlocks(blocks: MarkedImportBlock[]): ImportNode[] {
  return rebuildTreeFromMarks(blocks)
}
