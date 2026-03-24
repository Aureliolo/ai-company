/**
 * Auth state management (Zustand).
 *
 * Manages JWT token lifecycle, login/logout flows, user profile, and session
 * expiry. Token is persisted to localStorage with expiry tracking.
 */

import { create } from 'zustand'
import * as authApi from '@/api/endpoints/auth'
import { getErrorMessage, isAxiosError } from '@/utils/errors'
import type { HumanRole, UserInfoResponse } from '@/api/types'

// ── Module-scoped internals (not renderable state) ──────────

let expiryTimer: ReturnType<typeof setTimeout> | null = null

// Clean up timer during HMR to avoid stale timers on dev reloads
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    if (expiryTimer) {
      clearTimeout(expiryTimer)
      expiryTimer = null
    }
  })
}

// ── Store types ─────────────────────────────────────────────

interface AuthState {
  token: string | null
  user: UserInfoResponse | null
  loading: boolean
  /** Fallback for must_change_password when user is not yet loaded (page refresh). */
  _mustChangePasswordFallback: boolean

  setToken: (newToken: string, expiresIn: number) => void
  clearAuth: () => void
  login: (username: string, password: string) => Promise<void>
  setup: (username: string, password: string) => Promise<void>
  fetchUser: () => Promise<void>
  changePassword: (currentPassword: string, newPassword: string) => Promise<UserInfoResponse>
  logout: () => void
}

// ── Initial state from localStorage ─────────────────────────

function getInitialToken(): string | null {
  const storedToken = localStorage.getItem('auth_token')
  const expiresAt = Number(localStorage.getItem('auth_token_expires_at') ?? 0)
  if (storedToken && Date.now() < expiresAt) {
    return storedToken
  }
  localStorage.removeItem('auth_token')
  localStorage.removeItem('auth_token_expires_at')
  localStorage.removeItem('auth_must_change_password')
  return null
}

// ── Store ───────────────────────────────────────────────────

export const useAuthStore = create<AuthState>()((set, get) => {
  const initialToken = getInitialToken()

  // Schedule expiry cleanup for restored token
  if (initialToken) {
    const expiresAt = Number(localStorage.getItem('auth_token_expires_at') ?? 0)
    if (expiresAt > Date.now()) {
      expiryTimer = setTimeout(() => {
        get().clearAuth()
      }, expiresAt - Date.now())
    }
  }

  /** Common post-auth flow: set token, fetch user profile, handle failures. */
  async function performAuthFlow(
    authFn: () => Promise<{ token: string; expires_in: number }>,
    flowName: string,
  ): Promise<void> {
    set({ loading: true })
    try {
      const result = await authFn()
      get().setToken(result.token, result.expires_in)
      try {
        await get().fetchUser()
      } catch (fetchErr) {
        // fetchUser already calls clearAuth() on 401 before throwing
        if (!get().token) {
          throw new Error(`${flowName} failed: session expired. Please try again.`, { cause: fetchErr })
        }
        // Don't clear the fresh token on transient errors (network, 5xx).
        // The auth succeeded; the profile load can be retried.
        throw new Error(`${flowName} succeeded but failed to load user profile. Please check your connection and try again.`, { cause: fetchErr })
      }
      if (!get().user) {
        get().clearAuth()
        throw new Error(`${flowName} succeeded but failed to load user profile. Please try again.`)
      }
    } finally {
      set({ loading: false })
    }
  }

  return {
    token: initialToken,
    user: null,
    loading: false,
    _mustChangePasswordFallback: localStorage.getItem('auth_must_change_password') === 'true',

    setToken(newToken: string, expiresIn: number) {
      if (!Number.isFinite(expiresIn) || expiresIn <= 0) {
        throw new Error('Authentication failed: server returned invalid session duration. Please try again.')
      }
      // Clear any existing expiry timer
      if (expiryTimer) {
        clearTimeout(expiryTimer)
        expiryTimer = null
      }

      set({ token: newToken })
      const expiresAtMs = Date.now() + expiresIn * 1000
      localStorage.setItem('auth_token', newToken)
      localStorage.setItem('auth_token_expires_at', String(expiresAtMs))

      // Schedule token cleanup
      expiryTimer = setTimeout(() => {
        get().clearAuth()
      }, expiresIn * 1000)
    },

    clearAuth() {
      if (expiryTimer) {
        clearTimeout(expiryTimer)
        expiryTimer = null
      }
      set({ token: null, user: null, _mustChangePasswordFallback: false })
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_token_expires_at')
      localStorage.removeItem('auth_must_change_password')
      // Redirect to login if not already there
      // TODO: Phase 1.3 -- use react-router navigate
      if (window.location.pathname !== '/login' && window.location.pathname !== '/setup') {
        window.location.href = '/login'
      }
    },

    async login(username: string, password: string) {
      await performAuthFlow(() => authApi.login({ username, password }), 'Login')
    },

    async setup(username: string, password: string) {
      await performAuthFlow(() => authApi.setup({ username, password }), 'Setup')
    },

    async fetchUser() {
      if (!get().token) return
      try {
        const user = await authApi.getMe()
        set({ user })
        // Persist must_change_password for the auth guard on page refresh
        if (user?.must_change_password) {
          localStorage.setItem('auth_must_change_password', 'true')
          set({ _mustChangePasswordFallback: true })
        } else {
          localStorage.removeItem('auth_must_change_password')
          set({ _mustChangePasswordFallback: false })
        }
      } catch (err) {
        // Only clear auth on 401 (invalid/expired token)
        if (isAxiosError(err) && err.response?.status === 401) {
          console.warn('Session expired or invalid token -- clearing auth')
          get().clearAuth()
          throw new Error('Session expired. Please log in again.', { cause: err })
        } else {
          console.error('Failed to fetch user profile:', getErrorMessage(err))
          throw err
        }
      }
    },

    async changePassword(currentPassword: string, newPassword: string) {
      set({ loading: true })
      try {
        const result = await authApi.changePassword({
          current_password: currentPassword,
          new_password: newPassword,
        })
        set({ user: result })
        if (result && !result.must_change_password) {
          localStorage.removeItem('auth_must_change_password')
          set({ _mustChangePasswordFallback: false })
        }
        return result
      } catch (err) {
        throw new Error(getErrorMessage(err), { cause: err })
      } finally {
        set({ loading: false })
      }
    },

    logout() {
      get().clearAuth()
    },
  }
})

// ── Selector hooks ──────────────────────────────────────────

export const useIsAuthenticated = () => useAuthStore((s) => !!s.token)

export const useUserRole = () => useAuthStore((s): HumanRole | null => s.user?.role ?? null)

export const useMustChangePassword = () =>
  useAuthStore((s) =>
    s.user?.must_change_password ?? s._mustChangePasswordFallback,
  )
