import { useMemo } from 'react'
import { useAuthStore, useIsAuthenticated, useUserRole, useMustChangePassword } from '@/stores/auth'
import { WRITE_ROLES } from '@/utils/constants'
import type { HumanRole, UserInfoResponse } from '@/api/types'

/** Stable user selector to avoid inline function reference per render. */
const selectUser = (s: { user: UserInfoResponse | null }) => s.user

/** Auth state helpers for components. */
export function useAuth(): {
  isAuthenticated: boolean
  user: UserInfoResponse | null
  userRole: HumanRole | null
  mustChangePassword: boolean
  canWrite: boolean
} {
  const isAuthenticated = useIsAuthenticated()
  const user = useAuthStore(selectUser)
  const userRole = useUserRole()
  const mustChangePassword = useMustChangePassword()

  const canWrite = userRole !== null && (WRITE_ROLES as readonly string[]).includes(userRole)

  return useMemo(() => ({
    isAuthenticated,
    user,
    userRole,
    mustChangePassword,
    canWrite,
  }), [isAuthenticated, user, userRole, mustChangePassword, canWrite])
}
