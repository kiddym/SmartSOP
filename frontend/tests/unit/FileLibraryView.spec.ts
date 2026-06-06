import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { listLib, setHidden, dl, del } = vi.hoisted(() => ({
  listLib: vi.fn(),
  setHidden: vi.fn(),
  dl: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/attachments', () => ({
  listFileLibrary: listLib,
  setAttachmentHidden: setHidden,
  downloadAttachment: dl,
  deleteAttachment: del,
}))

import FileLibraryView from '@/views/admin/FileLibraryView.vue'
import type { LibraryAttachment } from '@/types/attachment'

function makeRow(over: Partial<LibraryAttachment> = {}): LibraryAttachment {
  return {
    id: 'a1',
    entity_type: 'asset',
    entity_id: 'e1',
    file_name: 'photo.png',
    mime_type: 'image/png',
    file_type: 'IMAGE',
    hidden: false,
    size_bytes: 2048,
    description: '',
    created_at: '2026-06-06T00:00:00',
    updated_at: '2026-06-06T00:00:00',
    ...over,
  }
}

function mountView() {
  return mount(FileLibraryView, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  listLib.mockReset().mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })
  setHidden.mockReset().mockResolvedValue(makeRow({ hidden: true }))
  dl.mockReset().mockResolvedValue(undefined)
  del.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('FileLibraryView', () => {
  it('挂载即拉取并列出文件（文件名/类型标签/实体标签）', async () => {
    listLib.mockResolvedValue({
      items: [makeRow(), makeRow({ id: 'a2', file_name: 'doc.pdf', file_type: 'OTHER', entity_type: 'work_order' })],
      total: 2,
      limit: 20,
      offset: 0,
    })
    mountView()
    await flushPromises()
    expect(listLib).toHaveBeenCalledTimes(1)
    const text = document.body.textContent ?? ''
    expect(text).toContain('photo.png')
    expect(text).toContain('doc.pdf')
    expect(text).toContain('图片')
    expect(text).toContain('资产')
    expect(text).toContain('工单')
  })

  it('关键字查询带 q 参数并重置到第 1 页', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as {
      filters: { q: string; file_type: string; entity_type: string; include_hidden: boolean }
      onSearch: () => void
    }
    vm.filters.q = '泵'
    vm.onSearch()
    await flushPromises()
    expect(listLib).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: '泵', limit: 20, offset: 0 }),
    )
  })

  it('类型/含隐藏过滤透传后端', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as {
      filters: { q: string; file_type: string; entity_type: string; include_hidden: boolean }
      onSearch: () => void
    }
    vm.filters.file_type = 'IMAGE'
    vm.filters.include_hidden = true
    vm.onSearch()
    await flushPromises()
    expect(listLib).toHaveBeenLastCalledWith(
      expect.objectContaining({ file_type: 'IMAGE', include_hidden: true }),
    )
  })

  it('隐藏切换调用 setAttachmentHidden(取反)并刷新', async () => {
    listLib.mockResolvedValue({ items: [makeRow()], total: 1, limit: 20, offset: 0 })
    const w = mountView()
    await flushPromises()
    listLib.mockClear()
    const vm = w.vm as unknown as {
      rows: LibraryAttachment[]
      onToggleHidden: (r: LibraryAttachment) => Promise<void>
    }
    await vm.onToggleHidden(vm.rows[0])
    await flushPromises()
    expect(setHidden).toHaveBeenCalledWith('a1', true)
    // 切换后重新拉取列表。
    expect(listLib).toHaveBeenCalled()
  })
})
