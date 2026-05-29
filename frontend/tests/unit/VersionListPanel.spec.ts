import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const { fetchGroupVersions } = vi.hoisted(() => ({ fetchGroupVersions: vi.fn() }))
vi.mock('@/api/procedures', () => ({ fetchGroupVersions }))

import VersionListPanel from '@/components/version/VersionListPanel.vue'
import type { VersionListItem } from '@/types/procedure'
import { ElMessage } from 'element-plus'

function item(o: Partial<VersionListItem> & { id: string; version: number }): VersionListItem {
  return {
    id: o.id,
    version: o.version,
    status: o.status ?? 'ARCHIVED',
    is_current: o.is_current ?? false,
    version_update_notes: o.version_update_notes ?? '',
    version_update_notes_preview: o.version_update_notes_preview ?? '',
    created_at: o.created_at ?? '2026-05-22T00:00:00',
    archived_at: o.archived_at ?? null,
  }
}

async function mountPanel(items: VersionListItem[], viewingId = 'v3') {
  fetchGroupVersions.mockResolvedValue({ count: items.length, items })
  const w = mount(VersionListPanel, {
    props: { groupId: 'g1', viewingId },
    global: { plugins: [ElementPlus] },
  })
  await flushPromises()
  return w
}

describe('VersionListPanel', () => {
  beforeEach(() => fetchGroupVersions.mockReset())

  it('渲染全部版本行 + 当前标记', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2 }),
      item({ id: 'v1', version: 1 }),
    ])
    expect(w.text()).toContain('v3')
    expect(w.text()).toContain('v1')
    expect(w.text()).toContain('当前')
  })

  it('存在当前已发布版本时，归档版本显示「回退到此版本」并带当前 id 派发', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2, status: 'ARCHIVED' }),
    ])
    const rollbackBtn = w.findAll('button').find((b) => b.text().includes('回退到此版本'))
    expect(rollbackBtn).toBeTruthy()
    await rollbackBtn!.trigger('click')
    expect(w.emitted('rollback')?.[0]).toEqual([2, 'v3'])
  })

  it('当前版本为草稿时不提供回退', async () => {
    const w = await mountPanel([
      item({ id: 'v2', version: 2, status: 'DRAFT', is_current: true }),
      item({ id: 'v1', version: 1, status: 'ARCHIVED' }),
    ])
    expect(w.findAll('button').some((b) => b.text().includes('回退到此版本'))).toBe(false)
  })

  it('点击查看派发 view（非当前查看行）', async () => {
    const w = await mountPanel(
      [
        item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
        item({ id: 'v2', version: 2 }),
      ],
      'v3',
    )
    const viewBtn = w.findAll('button').find((b) => b.text().trim() === '查看')
    await viewBtn!.trigger('click')
    expect(w.emitted('view')?.[0]).toEqual(['v2'])
  })

  it('有 notes 且折叠 → 渲染预览片段（version_update_notes_preview）', async () => {
    const w = await mountPanel(
      [item({ id: 'v2', version: 2, version_update_notes: '完整说明文本', version_update_notes_preview: '完整说明…' })],
      'v3',
    )
    const preview = w.find('.notes-preview')
    expect(preview.exists()).toBe(true)
    expect(preview.text()).toContain('完整说明…')
  })

  it('无 notes → 不渲染预览片段', async () => {
    const w = await mountPanel([item({ id: 'v2', version: 2 })], 'v3') // notes 默认 ''
    expect(w.find('.notes-preview').exists()).toBe(false)
  })

  it('展开后隐藏预览、显示完整说明', async () => {
    const w = await mountPanel(
      [item({ id: 'v2', version: 2, version_update_notes: '完整说明文本', version_update_notes_preview: '完整说明…' })],
      'v3',
    )
    const toggle = w.findAll('button').find((b) => b.text().includes('更新说明'))
    await toggle!.trigger('click')
    expect(w.find('.notes-preview').exists()).toBe(false)
    expect(w.find('.notes').text()).toContain('完整说明文本')
  })

  it('点击刷新 → 重新拉取并提示「已刷新」', async () => {
    const w = await mountPanel([item({ id: 'v1', version: 1 })])
    const successSpy = vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
    fetchGroupVersions.mockResolvedValue({ count: 1, items: [item({ id: 'v1', version: 1 })] })
    const refreshBtn = w.findAll('button').find((b) => b.text().trim() === '刷新')
    await refreshBtn!.trigger('click')
    await flushPromises()
    expect(fetchGroupVersions).toHaveBeenCalledTimes(2) // mount + 手动刷新
    expect(successSpy).toHaveBeenCalledWith('已刷新')
  })

  it('非当前行显示「对比当前」并派发 compare（older→current）', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2, status: 'ARCHIVED' }),
    ], 'v3')
    const btn = w.findAll('button').find((b) => b.text().includes('对比当前'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(w.emitted('compare')?.[0]).toEqual([{ oldId: 'v2', oldVersion: 2, newId: 'v3', newVersion: 3 }])
  })

  it('当前行不显示「对比当前」', async () => {
    const w = await mountPanel([item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true })], 'v3')
    expect(w.findAll('button').some((b) => b.text().includes('对比当前'))).toBe(false)
  })

  it('对比所选: pick two out of order → emits the version-ordered pair (old=lower)', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2, status: 'ARCHIVED' }),
      item({ id: 'v1', version: 1, status: 'ARCHIVED' }),
    ], 'v3')
    const checks = w.findAllComponents({ name: 'ElCheckbox' }) // one per row, in item order
    checks[0].vm.$emit('change', true) // v3
    checks[2].vm.$emit('change', true) // v1
    await w.vm.$nextTick()
    const btn = w.findAll('button').find((b) => b.text().includes('对比所选'))
    expect(btn?.attributes('disabled')).toBeUndefined() // enabled at exactly 2
    await btn!.trigger('click')
    expect(w.emitted('compare')?.[0]).toEqual([
      { oldId: 'v1', oldVersion: 1, newId: 'v3', newVersion: 3 },
    ])
  })

  it('对比所选 is disabled unless exactly two are selected', async () => {
    const w = await mountPanel([
      item({ id: 'v2', version: 2, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v1', version: 1, status: 'ARCHIVED' }),
    ], 'v2')
    expect(w.findAll('button').some((b) => b.text().includes('对比所选'))).toBe(false) // none selected → no bar
    w.findAllComponents({ name: 'ElCheckbox' })[0].vm.$emit('change', true) // 1 selected
    await w.vm.$nextTick()
    const btn = w.findAll('button').find((b) => b.text().includes('对比所选'))
    expect(btn?.attributes('disabled')).toBeDefined() // present but disabled
  })

  it('selection caps at two (FIFO drops the earliest pick)', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2, status: 'ARCHIVED' }),
      item({ id: 'v1', version: 1, status: 'ARCHIVED' }),
    ], 'v3')
    const checks = w.findAllComponents({ name: 'ElCheckbox' })
    checks[0].vm.$emit('change', true) // v3
    checks[1].vm.$emit('change', true) // v2
    checks[2].vm.$emit('change', true) // v1 → drops v3 (FIFO) → [v2, v1]
    await w.vm.$nextTick()
    await w.findAll('button').find((b) => b.text().includes('对比所选'))!.trigger('click')
    expect(w.emitted('compare')?.[0]).toEqual([
      { oldId: 'v1', oldVersion: 1, newId: 'v2', newVersion: 2 },
    ])
  })
})
