import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { gcs, ucs, lc } = vi.hoisted(() => ({
  gcs: vi.fn(),
  ucs: vi.fn(),
  lc: vi.fn(),
}))
vi.mock('@/api/companySettings', () => ({
  getCompanySettings: gcs,
  updateCompanySettings: ucs,
}))
vi.mock('@/api/currencies', () => ({ listCurrencies: lc }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => true, user: { role_code: 'admin' } }),
}))

import CompanySettingsView from '@/views/platform/CompanySettingsView.vue'

function mountView() {
  return mount(CompanySettingsView, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  gcs.mockReset().mockResolvedValue({
    date_format: 'YYYY-MM-DD',
    timezone: 'Asia/Shanghai',
    default_currency_code: 'CNY',
    auto_assign: true,
  })
  ucs.mockReset().mockResolvedValue({
    date_format: 'YYYY-MM-DD',
    timezone: 'Asia/Tokyo',
    default_currency_code: 'CNY',
    auto_assign: true,
  })
  lc.mockReset().mockResolvedValue([{ id: 'c1', code: 'CNY', name: '人民币', symbol: '¥' }])
})

describe('CompanySettingsView', () => {
  it('载入时调用 getCompanySettings 并回填表单', async () => {
    const w = mountView()
    await flushPromises()
    expect(gcs).toHaveBeenCalled()
    expect(lc).toHaveBeenCalled()
    const tzInput = w
      .findAll('input')
      .find((i) => i.attributes('placeholder') === '如 Asia/Shanghai')
    expect(tzInput).toBeTruthy()
    expect((tzInput!.element as HTMLInputElement).value).toBe('Asia/Shanghai')
  })

  it('保存时调用 updateCompanySettings 并携带改动字段', async () => {
    const w = mountView()
    await flushPromises()

    const tzInput = w
      .findAll('input')
      .find((i) => i.attributes('placeholder') === '如 Asia/Shanghai')
    expect(tzInput).toBeTruthy()
    await tzInput!.setValue('Asia/Tokyo')
    await flushPromises()

    const saveBtn = w.findAll('.el-button').find((b) => b.text() === '保存')
    expect(saveBtn).toBeTruthy()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(ucs).toHaveBeenCalledWith(
      expect.objectContaining({
        date_format: 'YYYY-MM-DD',
        timezone: 'Asia/Tokyo',
        default_currency_code: 'CNY',
        auto_assign: true,
      }),
    )
  })
})
