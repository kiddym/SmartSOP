import type { RouteLocationNormalized, RouteLocationRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const PUBLIC_NAMES = new Set(['login', 'register'])

export async function authGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
): Promise<boolean | RouteLocationRaw> {
  const auth = useAuthStore()
  await auth.bootstrap() // 幂等，确保刷新页恢复完成再判定

  const isPublic = typeof to.name === 'string' && PUBLIC_NAMES.has(to.name)

  if (auth.isAuthenticated && isPublic) {
    return { path: '/' }
  }
  if (!auth.isAuthenticated && to.meta.requiresAuth) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
}
