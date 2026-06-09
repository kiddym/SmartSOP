import { describe, it, expect } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routes } from '@/router/routes'

function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

describe('组织设置路由', () => {
  it('新增 /admin/config/organization 可解析且 name 为 config-organization', async () => {
    const r = makeRouter()
    await r.push('/admin/config/organization')
    expect(r.currentRoute.value.matched.length).toBeGreaterThan(0)
    expect(r.currentRoute.value.name).toBe('config-organization')
  })

  it('旧设置路由 redirect 到聚合页对应 tab', async () => {
    const cases: [string, string][] = [
      ['/admin/company', 'company'],
      ['/admin/settings', 'global'],
    ]
    const r = makeRouter()
    for (const [from, tab] of cases) {
      await r.push(from)
      expect(r.currentRoute.value.path).toBe('/admin/config/organization')
      expect(r.currentRoute.value.query.tab).toBe(tab)
    }
  })

  it('既有别名 redirect 双跳仍达组织设置', async () => {
    const r = makeRouter()
    await r.push('/platform/settings') // → /admin/company → ?tab=company
    expect(r.currentRoute.value.path).toBe('/admin/config/organization')
    expect(r.currentRoute.value.query.tab).toBe('company')
    await r.push('/settings') // → /admin/settings → ?tab=global
    expect(r.currentRoute.value.path).toBe('/admin/config/organization')
    expect(r.currentRoute.value.query.tab).toBe('global')
  })

  it('客户/供应商 route name 已对齐 partners-*', async () => {
    const r = makeRouter()
    await r.push('/maintenance/customers')
    expect(r.currentRoute.value.name).toBe('partners-customers')
    await r.push('/inventory/vendors')
    expect(r.currentRoute.value.name).toBe('partners-vendors')
  })
})
