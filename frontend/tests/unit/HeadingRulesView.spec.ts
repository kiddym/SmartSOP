import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const { list, create, update, del, plist, pcreate, pupdate, pdel } = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  del: vi.fn(),
  plist: vi.fn(),
  pcreate: vi.fn(),
  pupdate: vi.fn(),
  pdel: vi.fn(),
}))
vi.mock('@/api/headingRules', () => ({
  listHeadingRules: list,
  createHeadingRule: create,
  updateHeadingRule: update,
  deleteHeadingRule: del,
}))
vi.mock('@/api/numberingProfiles', () => ({
  listNumberingProfiles: plist,
  createNumberingProfile: pcreate,
  updateNumberingProfile: pupdate,
  deleteNumberingProfile: pdel,
}))

import HeadingRulesView from '@/views/settings/HeadingRulesView.vue'

function rule(over: Record<string, unknown> = {}) {
  return {
    id: 'r1',
    style_name: '章节标题',
    level: 1,
    source: 'learned',
    status: 'active',
    level_votes: { '1': 3 },
    evidence_count: 3,
    agreement: 1.0,
    revision: 1,
    created_at: '',
    updated_at: '',
    ...over,
  }
}

function profile(over: Record<string, unknown> = {}) {
  return {
    id: 'np1',
    pattern_key: '第X条',
    kind: 'heading',
    level: 3,
    source: 'manual',
    status: 'active',
    level_votes: {},
    evidence_count: 0,
    agreement: 0,
    revision: 1,
    created_at: '',
    updated_at: '',
    ...over,
  }
}

function mountView() {
  return mount(HeadingRulesView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  list.mockReset().mockResolvedValue([rule()])
  create.mockReset().mockResolvedValue(rule())
  update.mockReset().mockResolvedValue(rule())
  del.mockReset().mockResolvedValue(undefined)
  plist.mockReset().mockResolvedValue([profile()])
  pcreate.mockReset().mockResolvedValue(profile())
  pupdate.mockReset().mockResolvedValue(profile())
  pdel.mockReset().mockResolvedValue(undefined)
})

describe('HeadingRulesView', () => {
  it('loads rules on mount and renders the style name + evidence', async () => {
    const w = mountView()
    await flushPromises()
    expect(list).toHaveBeenCalled()
    expect(w.text()).toContain('章节标题')
    expect(w.text()).toContain('100%') // agreement
  })

  it('adds a manual rule via the create API', async () => {
    const w = mountView()
    await flushPromises()
    await w.find('.add-name input').setValue('公司标题')
    await w.find('.add-btn').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith('公司标题', 1)
  })

  it('toggling status calls update with the opposite status', async () => {
    const w = mountView()
    await flushPromises()
    // 第一个操作按钮 = 停用（当前 active）
    const toggle = w.findAll('.rules-table .el-button').find((b) => b.text() === '停用')
    expect(toggle).toBeTruthy()
    await toggle!.trigger('click')
    await flushPromises()
    expect(update).toHaveBeenCalledWith('r1', { status: 'disabled' })
  })

  it('loads numbering profiles and renders the pattern key', async () => {
    const w = mountView()
    await flushPromises()
    expect(plist).toHaveBeenCalled()
    expect(w.text()).toContain('第X条')
    expect(w.text()).toContain('编号体例')
  })

  it('toggling a numbering profile status calls updateNumberingProfile', async () => {
    const w = mountView()
    await flushPromises()
    const toggle = w.findAll('.profiles-table .el-button').find((b) => b.text() === '停用')
    expect(toggle).toBeTruthy()
    await toggle!.trigger('click')
    await flushPromises()
    expect(pupdate).toHaveBeenCalledWith('np1', { status: 'disabled' })
  })
})
