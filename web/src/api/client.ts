/**
 * Axios client with JWT interceptor and ApiResponse envelope unwrapping.
 */

import axios, { type AxiosError, type AxiosResponse } from 'axios'
import type { ApiResponse, ErrorDetail, PaginatedResponse } from './types'
import { sanitizeForLog } from '@/utils/logging'

// Normalize: strip trailing slashes and any existing /api/v1 suffix
const RAW_BASE = (import.meta.env.VITE_API_BASE_URL as string) || ''
const BASE_URL = RAW_BASE.replace(/\/+$/, '').replace(/\/api\/v1\/?$/, '')

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// ── Request interceptor: attach JWT ──────────────────────────
// SECURITY NOTE: JWT is stored in localStorage, which is accessible to any JS
// running in the page context (XSS risk). HttpOnly cookies would eliminate this
// attack surface but require backend cookie-based auth support plus CSRF
// protection. Mitigations in place: short-lived tokens with server-controlled
// expiry, automatic 401 cleanup, and expiry checks on page load (see auth
// store). CSP headers in nginx.conf restrict script sources. If the deployment
// architecture changes to support cookie-based auth, migrate away from
// localStorage -- see docs/security.md for the full threat model.

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: 401 redirect + error passthrough ──

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<{ error?: string; success?: boolean }>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_token_expires_at')
      localStorage.removeItem('auth_must_change_password')
      // Sync Pinia auth state -- dynamic import avoids circular dependency
      import('@/stores/auth').then(({ useAuthStore }) => {
        const auth = useAuthStore()
        // clearAuth() also handles redirect to /login
        auth.logout()
      }).catch((importErr: unknown) => {
        console.error('Failed to import auth store after 401:', sanitizeForLog(importErr))
        // Fallback if store import fails: redirect directly
        if (window.location.pathname !== '/login' && window.location.pathname !== '/setup') {
          window.location.href = '/login'
        }
      })
      // On setup page, re-fetch status to handle backend reset or token expiry.
      // Guard: skip if the failing request was itself /setup/status to prevent
      // unbounded 401 loops (the status endpoint is normally unauthenticated,
      // but a misconfigured backend could still return 401).
      const requestUrl = error.config?.url ?? ''
      if (
        window.location.pathname === '/setup' &&
        !/\/setup\/status(\?|$)/.test(requestUrl)
      ) {
        import('@/stores/setup').then(({ useSetupStore }) => {
          const setup = useSetupStore()
          return setup.fetchStatus()
        }).catch((err: unknown) => {
          // Best-effort: setup status re-fetch is non-critical after 401
          console.warn('Failed to re-fetch setup status after 401:', sanitizeForLog(err))
        })
      }
    }
    return Promise.reject(error)
  },
)

/**
 * Error thrown when the API returns an error response.
 * Carries the structured RFC 9457 error detail when available.
 */
export class ApiRequestError extends Error {
  readonly errorDetail: ErrorDetail | null

  constructor(message: string, errorDetail: ErrorDetail | null = null) {
    super(message)
    this.name = 'ApiRequestError'
    this.errorDetail = errorDetail
  }
}

/**
 * Extract data from an ApiResponse envelope.
 * Throws if the response indicates an error.
 */
export function unwrap<T>(response: AxiosResponse<ApiResponse<T>>): T {
  const body = response.data
  if (!body || typeof body !== 'object') {
    throw new ApiRequestError('Unknown API error')
  }
  if (!body.success || body.data === null || body.data === undefined) {
    const detail = 'error_detail' in body ? (body.error_detail as ErrorDetail | null) : null
    throw new ApiRequestError(body.error ?? 'Unknown API error', detail)
  }
  return body.data
}

/**
 * Validate an ApiResponse envelope without extracting data.
 * Use for endpoints that return {@code ApiResponse<null>}.
 */
export function unwrapVoid(response: AxiosResponse<ApiResponse<null>>): void {
  const body = response.data
  if (!body || typeof body !== 'object') {
    throw new ApiRequestError('Unknown API error')
  }
  if (!body.success) {
    const detail = 'error_detail' in body ? (body.error_detail as ErrorDetail | null) : null
    throw new ApiRequestError(body.error ?? 'Unknown API error', detail)
  }
}

/**
 * Extract data from a paginated response.
 * Validates the response structure to avoid cryptic TypeErrors.
 */
export function unwrapPaginated<T>(
  response: AxiosResponse<PaginatedResponse<T>>,
): { data: T[]; total: number; offset: number; limit: number } {
  const body = response.data
  if (!body || typeof body !== 'object') {
    throw new Error('Unknown API error')
  }
  if (!body.success) {
    const detail = 'error_detail' in body ? (body.error_detail as ErrorDetail | null) : null
    throw new ApiRequestError(body.error ?? 'Unknown API error', detail)
  }
  if (!body.pagination || !Array.isArray(body.data)) {
    throw new Error('Unexpected API response format')
  }
  return {
    data: body.data,
    total: body.pagination.total,
    offset: body.pagination.offset,
    limit: body.pagination.limit,
  }
}
