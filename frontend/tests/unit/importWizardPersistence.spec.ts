import { beforeEach, describe, expect, it } from 'vitest'
import {
  WIZARD_KEY,
  WIZARD_TTL_MS,
  clearWizard,
  loadWizard,
  saveWizard,
  type WizardSnapshot,
} from '@/composables/useImportWizardPersistence'
import type { MarkedImportBlock } from '@/utils/importBlocks'

function markedBlock(): MarkedImportBlock {
  return {
    id: 'block-1',
    source_index: 1,
    raw_text: '目的',
    display_text: '目的',
    clean_text: '目的',
    rich_content: '<p>目的</p>',
    block_type: 'paragraph',
    has_word_numbering: false,
    word_number: null,
    word_number_level: null,
    style_name: null,
    suggested_type: 'chapter',
    suggested_level: 1,
    confidence_tier: 'high',
    mark_status: 'unmarked',
    assigned_role: 'chapter_1',
  }
}

function snap(createdAt: string): WizardSnapshot {
  return {
    created_at: createdAt,
    step: 3,
    upload_token: 'tok-1',
    filename: '记录控制程序.docx',
    parse_mode: 'smart',
    parse_result: null,
    tree: [],
    marked_blocks: [markedBlock()],
    form: { name: '记录控制程序', folder_id: 'f1' },
  }
}

describe('导入向导 sessionStorage 持久化', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('save 后 load 回读同一快照', () => {
    const s = snap(new Date().toISOString())
    saveWizard(s)
    expect(sessionStorage.getItem(WIZARD_KEY)).toBeTruthy()
    const loaded = loadWizard()
    expect(loaded?.upload_token).toBe('tok-1')
    expect(loaded?.step).toBe(3)
    expect(loaded?.marked_blocks).toHaveLength(1)
    expect(loaded?.marked_blocks[0].assigned_role).toBe('chapter_1')
  })

  it('无存储时 load 返回 null', () => {
    expect(loadWizard()).toBeNull()
  })

  it('超过 24h 的快照 load 返回 null 并清除', () => {
    const old = new Date(Date.now() - WIZARD_TTL_MS - 1000).toISOString()
    saveWizard(snap(old))
    expect(loadWizard()).toBeNull()
    expect(sessionStorage.getItem(WIZARD_KEY)).toBeNull()
  })

  it('24h 内的快照仍可恢复', () => {
    const recent = new Date(Date.now() - WIZARD_TTL_MS + 60_000).toISOString()
    saveWizard(snap(recent))
    expect(loadWizard()?.upload_token).toBe('tok-1')
  })

  it('损坏 JSON 时 load 返回 null 并清除', () => {
    sessionStorage.setItem(WIZARD_KEY, '{not json')
    expect(loadWizard()).toBeNull()
    expect(sessionStorage.getItem(WIZARD_KEY)).toBeNull()
  })

  it('clear 移除键', () => {
    saveWizard(snap(new Date().toISOString()))
    clearWizard()
    expect(sessionStorage.getItem(WIZARD_KEY)).toBeNull()
  })
})
