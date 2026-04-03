/**
 * Axios client with JWT interceptor and ApiResponse envelope unwrapping.
 */

import axios, { type AxiosError, type AxiosResponse } from 'axios'
import { createLogger } from '@/lib/logger'
import { IS_DEV_AUTH_BYPASS } from '@/utils/dev'
import type { ApiResponse, ErrorDetail, PaginatedResponse } from './types'

const log = createLogger('api-client')

// Normalize: strip trailing slashes and any existing /api/v1 suffix
const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
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
// store). Default token lifetime is 24 hours (configurable via jwt_expiry_minutes).
// CSP headers in security-headers.conf (included by nginx.conf) restrict
// script sources. If the deployment
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
    if (error.response?.status === 401 && !IS_DEV_AUTH_BYPASS) {
      // Clear credentials synchronously to prevent stale-token retries
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_token_expires_at')
      localStorage.removeItem('auth_must_change_password')
      // Sync Zustand auth state -- dynamic import avoids circular dependency.
      // We intentionally fire-and-forget: the rejection below reaches the
      // caller immediately, while auth state cleanup happens concurrently.
      import('@/stores/auth').then(({ useAuthStore }) => {
        useAuthStore.getState().logout()
      }).catch((importErr: unknown) => {
        log.error('Auth store cleanup failed during 401 handling:', importErr)
        // Fallback if store import fails: redirect directly
        if (window.location.pathname !== '/login' && window.location.pathname !== '/setup') {
          window.location.href = '/login'
        }
      })
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
 * Use for endpoints that return `ApiResponse<null>` (including 204 No Content).
 */
export function unwrapVoid(response: AxiosResponse<ApiResponse<null>>): void {
  // 204 No Content: empty body is expected and valid
  if (response.status === 204) return
  const body = response.data
  if (!body || typeof body !== 'object') {
    throw new ApiRequestError('Unknown API error')
  }
  if (!body.success) {
    const detail = 'error_detail' in body ? (body.error_detail as ErrorDetail | null) : null
    throw new ApiRequestError(body.error ?? 'Unknown API error', detail)
  }
}

/** Return type for paginated API calls. */
export interface PaginatedResult<T> {
  data: T[]
  total: number
  offset: number
  limit: number
}

/**
 * Extract data from a paginated response.
 * Validates the response structure to avoid cryptic TypeErrors.
 */
export function unwrapPaginated<T>(
  response: AxiosResponse<PaginatedResponse<T>>,
): PaginatedResult<T> {
  const body = response.data
  if (!body || typeof body !== 'object') {
    throw new ApiRequestError('Unknown API error')
  }
  if (!body.success) {
    const detail = 'error_detail' in body ? (body.error_detail as ErrorDetail | null) : null
    throw new ApiRequestError(body.error ?? 'Unknown API error', detail)
  }
  if (!body.pagination || !Array.isArray(body.data)) {
    throw new ApiRequestError('Unexpected API response format')
  }
  return {
    data: body.data,
    total: body.pagination.total,
    offset: body.pagination.offset,
    limit: body.pagination.limit,
  }
}
