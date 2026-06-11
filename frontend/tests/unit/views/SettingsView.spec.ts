import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import SettingsView from '@/views/settings/SettingsView.vue'
import * as settingsApi from '@/api/settings'
import type { SettingsOut } from '@/types/settings'

const base: SettingsOut = {
  id: 's1',
  enable_version_control: true,
  enable_approval_workflow: false,
  max_version_number: 100,
  require_read_confirmation: false,
  default_risk_level: 1,
  default_quality_level: 1,
  revision: 5,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  auto_archive_days: 365,
}

function mountView() {
  return mount(SettingsView, { global: { plugins: [ElementPlus, i18n] } })
}

describe('SettingsView 冲突处理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('在 409 冲突时刷新设置', async () => {
    const getSpy = vi.spyOn(settingsApi, 'getSettings').mockResolvedValue({ ...base })
    vi.spyOn(settingsApi, 'updateSettings').mockRejectedValueOnce({ response: { status: 409 } })

    const w = mountView()
    await flushPromises() // initial load
    getSpy.mockClear()

    await w.find('[data-test="save"]').trigger('click')
    await flushPromises()

    expect(getSpy).toHaveBeenCalled() // 409 → reload to refresh revision
  })
})
