import { describe, it, expect } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routes } from '@/router/routes'

// router/index.ts 须导出 routes 供测试复用（见 Step 3）。
function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

const REDIRECTS: Array<[string, string]> = [
  ['/folders', '/procedures/folders'],
  ['/maindata/assets', '/assets'],
  ['/maindata/locations', '/assets/locations'],
  ['/inventory/multi-parts', '/inventory/parts/kits'],
  ['/inventory/customers', '/maintenance/customers'],
  ['/platform/users', '/admin/users'],
  ['/platform/roles', '/admin/roles'],
  ['/platform/teams', '/admin/teams'],
  // 公司设置/系统设置已合并为组织设置聚合页,旧别名经二次跳转最终落到 /admin/config/organization。
  ['/platform/settings', '/admin/config/organization'],
  ['/admin/company', '/admin/config/organization'],
  ['/platform/currencies', '/admin/currencies'],
  ['/settings', '/admin/config/organization'],
  ['/admin/settings', '/admin/config/organization'],
  // 字段路由已迁至配置中心聚合页，双跳后最终落到对应聚合页。
  ['/settings/fields', '/admin/config/sop'],
  ['/settings/heading-rules', '/admin/config/sop'],
  ['/audit-logs', '/admin/audit-logs'],
]

describe('router 旧路径重定向', () => {
  it.each(REDIRECTS)('%s 重定向到 %s', async (oldPath, newPath) => {
    const router = makeRouter()
    await router.push(oldPath)
    await router.isReady()
    expect(router.currentRoute.value.path).toBe(newPath)
  })

  const NEW_PATHS = [
    '/procedures/folders', '/assets', '/assets/locations',
    '/inventory/parts/kits', '/maintenance/customers',
    '/admin/users', '/admin/roles', '/admin/teams', '/admin/config/organization',
    '/admin/currencies', '/admin/audit-logs',
  ]
  // 注:/admin/fields、/admin/heading-rules 等旧字段路径已转为 redirect(指向配置中心聚合页 tab),
  // 其解析覆盖见 configRoutes.spec.ts「配置中心路由」。
  it.each(NEW_PATHS)('新路径 %s 可解析到已命名路由', async (p) => {
    const router = makeRouter()
    await router.push(p)
    await router.isReady()
    expect(router.currentRoute.value.matched.length).toBeGreaterThan(0)
    expect(router.currentRoute.value.name).toBeTruthy()
  })

  it('/inventory/parts/kits 不被 /inventory/parts/:id 遮蔽', async () => {
    const router = makeRouter()
    await router.push('/inventory/parts/kits')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('inventory-multi-parts')
    expect(router.currentRoute.value.params.id).toBeUndefined()
  })

  it('/inventory/parts/:id 解析到备件详情路由', async () => {
    const router = makeRouter()
    await router.push('/inventory/parts/p1')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('inventory-part-detail')
    expect(router.currentRoute.value.params.id).toBe('p1')
  })
})
