import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/store/auth'
import { usePermission } from '@/composables/usePermission'

describe('usePermission', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('代理 store.hasPermission', () => {
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'n', company_id: 'c', role_code: 'viewer', permissions: ['asset.view'] }
    const { hasPermission } = usePermission()
    expect(hasPermission('asset.view')).toBe(true)
    expect(hasPermission('asset.edit')).toBe(false)
  })
})
