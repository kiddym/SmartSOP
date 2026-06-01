import { useAuthStore } from '@/store/auth'

export function usePermission(): { hasPermission: (code: string) => boolean } {
  const auth = useAuthStore()
  return {
    hasPermission: (code: string): boolean => auth.hasPermission(code),
  }
}
