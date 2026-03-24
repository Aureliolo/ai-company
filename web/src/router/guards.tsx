import { useEffect } from 'react'
import { Navigate, Outlet } from 'react-router'
import { useIsAuthenticated } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'
import { ROUTES } from './routes'

/**
 * Requires authentication. Redirects to /login if no JWT token.
 * Renders child routes via <Outlet /> when authenticated.
 */
export function AuthGuard() {
  const isAuthenticated = useIsAuthenticated()

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />
  }

  return <Outlet />
}

/**
 * Requires setup to be complete. Redirects to /setup if not.
 * Shows a loading indicator while fetching setup status.
 * Must be nested inside AuthGuard (setup check only applies to authenticated users).
 */
export function SetupGuard() {
  const { setupComplete, loading, fetchSetupStatus } = useSetupStore()

  useEffect(() => {
    if (setupComplete === null && !loading) {
      fetchSetupStatus()
    }
  }, [setupComplete, loading, fetchSetupStatus])

  if (setupComplete === null || loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-text-secondary text-sm">Loading...</div>
      </div>
    )
  }

  if (!setupComplete) {
    return <Navigate to={ROUTES.SETUP} replace />
  }

  return <Outlet />
}

/**
 * Guest-only guard for /login. Redirects to dashboard if already authenticated.
 */
export function GuestGuard({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useIsAuthenticated()

  if (isAuthenticated) {
    return <Navigate to={ROUTES.DASHBOARD} replace />
  }

  return <>{children}</>
}

/**
 * Prevents access to /setup when setup is already complete.
 * Allows unauthenticated access (setup page may be shown before first login).
 */
export function SetupCompleteGuard({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useIsAuthenticated()
  const { setupComplete, loading, fetchSetupStatus } = useSetupStore()

  useEffect(() => {
    if (isAuthenticated && setupComplete === null && !loading) {
      fetchSetupStatus()
    }
  }, [isAuthenticated, setupComplete, loading, fetchSetupStatus])

  // If not authenticated, allow through (setup page handles its own auth flow)
  if (!isAuthenticated) {
    return <>{children}</>
  }

  // Authenticated -- check setup status
  if (setupComplete === null || loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-text-secondary text-sm">Loading...</div>
      </div>
    )
  }

  if (setupComplete) {
    return <Navigate to={ROUTES.DASHBOARD} replace />
  }

  return <>{children}</>
}
