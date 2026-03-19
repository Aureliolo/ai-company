import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'

/**
 * Navigation guard that handles setup flow and authentication.
 *
 * Priority order:
 * 1. Setup check -- if status not yet fetched, fetch it first (fail-closed)
 * 2. Setup redirect -- if setup is needed, redirect non-setup routes to /setup
 * 3. Auth check -- unauthenticated users go to /login for protected routes
 * 4. Password change enforcement -- mustChangePassword forces settings page
 *
 * The /setup route is always accessible when setup is needed, regardless of
 * auth status. When setup is complete, /setup redirects to /.
 * When status is null (not yet fetched), the guard fetches it before deciding.
 */
export async function authGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext,
): Promise<void> {
  const auth = useAuthStore()
  const setup = useSetupStore()

  // ── Setup routing ────────────────────────────────────────
  // Eagerly fetch setup status so routing decisions are never based
  // on stale/missing data.  Errors are logged inside the store;
  // fail-closed (isSetupNeeded defaults to true when fetch fails).

  if (setup.status === null && !setup.loading) {
    await setup.fetchStatus()
  }

  if (setup.status !== null) {
    // Setup is needed -- funnel everything to /setup
    if (setup.isSetupNeeded) {
      if (to.name !== 'setup' && to.name !== 'login') {
        next({ name: 'setup' })
        return
      }
      // Allow /setup and /login to proceed
      next()
      return
    }

    // Setup is complete -- redirect /setup to /
    if (to.name === 'setup') {
      next('/')
      return
    }
  }

  // ── Auth routing ─────────────────────────────────────────

  if (to.meta.requiresAuth === false) {
    // If already authenticated, redirect away from login
    if (auth.isAuthenticated) {
      next('/')
      return
    }
    next()
    return
  }

  if (!auth.isAuthenticated) {
    const redirect = to.fullPath !== '/' ? to.fullPath : undefined
    next({ path: '/login', query: redirect ? { redirect } : undefined })
    return
  }

  // Enforce mustChangePassword -- always normalize to settings?tab=user (password form)
  if (auth.mustChangePassword && !(to.name === 'settings' && to.query.tab === 'user')) {
    next({ name: 'settings', query: { tab: 'user' } })
    return
  }

  next()
}
