import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'

/**
 * Navigation guard that handles setup flow and authentication.
 *
 * Priority order:
 * 1. Setup check -- if setup is needed, redirect non-setup routes to /setup
 * 2. Auth check -- unauthenticated users go to /login for protected routes
 * 3. Password change enforcement -- mustChangePassword forces settings page
 *
 * The /setup route is always accessible when setup is needed, regardless of
 * auth status. When setup is complete, /setup redirects to /.
 */
export function authGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext,
): void {
  const auth = useAuthStore()
  const setup = useSetupStore()

  // ── Setup routing ────────────────────────────────────────
  // If status hasn't been fetched yet (null), allow navigation to proceed.
  // The setup page will fetch on mount; other pages work normally until
  // status is known.

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
