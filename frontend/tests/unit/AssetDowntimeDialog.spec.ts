import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { ld, ad, cd } = vi.hoisted(() => ({ ld: vi.fn(), ad: vi.fn(), cd: vi.fn() }))
vi.mock('@/api/assets', () => ({ listDowntimes: ld, addDowntime: ad, closeDowntime: cd }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))

import AssetDowntimeDialog from '@/components/maindata/AssetDowntimeDialog.vue'

const asset = { id: 'a1', name: '泵 1', custom_id: 'A-001' }

beforeEach(() => {
  setActivePinia(createPinia())
  ld.mockReset().mockResolvedValue([
    {
      id: 'd1',
      asset_id: 'a1',
      started_at: '2026-06-01T08:00:00',
      ended_at: null,
      reason: '故障',
      downtime_type: 'manual',
      source_asset_id: null,
    },
  ])
  ad.mockReset().mockResolvedValue({})
  cd.mockReset().mockResolvedValue({})
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('AssetDowntimeDialog', () => {
  it('可见时加载并渲染停机历史', async () => {
    mount(AssetDowntimeDialog, {
      props: { visible: true, asset, nameOf: () => '—' },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(ld).toHaveBeenCalledWith('a1')
    expect(document.body.textContent).toContain('故障')
  })

  it('关闭未结束停机调用 closeDowntime', async () => {
    const w = mount(AssetDowntimeDialog, {
      props: { visible: true, asset, nameOf: () => '—' },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()
    const closeBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '关闭',
    ) as HTMLElement
    expect(closeBtn).toBeTruthy()
    closeBtn.click()
    await flushPromises()
    const confirmBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '确认关闭',
    ) as HTMLElement
    confirmBtn.click()
    await flushPromises()
    expect(cd).toHaveBeenCalled()
    expect(cd.mock.calls[0][0]).toBe('a1')
    expect(w.emitted('changed')).toBeTruthy()
  })
})
