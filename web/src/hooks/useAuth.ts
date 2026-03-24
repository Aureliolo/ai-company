import { useAuthStore, useIsAuthenticated, useUserRole, useMustChangePassword } from '@/stores/auth'
import { WRITE_ROLES } from '@/utils/constants'
import type { HumanRole, UserInfoResponse } from '@/api/types'

/** Auth state helpers for components. */
export function useAuth(): {
  isAuthenticated: boolean
  user: UserInfoResponse | null
  userRole: HumanRole | null
  mustChangePassword: boolean
  canWrite: boolean
} {
  const isAuthenticated = useIsAuthenticated()
  const user = useAuthStore((s) => s.user)
  const userRole = useUserRole()
  const mustChangePassword = useMustChangePassword()

  const canWrite = userRole !== null && (WRITE_ROLES as readonly string[]).includes(userRole)

  return {
    isAuthenticated,
    user,
    userRole,
    mustChangePassword,
    canWrite,
  }
}
