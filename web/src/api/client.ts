/**
 * Axios client with cookie-based auth and ApiResponse envelope unwrapping.
 */

import axios, { type AxiosError, type AxiosResponse } from 'axios'
import { createLogger } from '@/lib/logger'
import { IS_DEV_AUTH_BYPASS } from '@/utils/dev'
import { getCsrfToken } from '@/utils/csrf'
import type { ApiResponse, ErrorDetail, PaginatedResponse } from './types'

const log = createLogger('api-client')

// Normalize: strip trailing slashes and any existing /api/v1 suffix
const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const BASE_URL = RAW_BASE.replace(/\/+$/, '').replace(/\/api\/v1\/?$/, '')

/** CSRF-protected HTTP methods that require the X-CSRF-Token header. */
const CSRF_METHODS = new Set(['post', 'put', 'patch', 'delete'])

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
  withCredentials: true,
})

// ── Request interceptor: attach CSRF token ─────────────────
// SECURITY NOTE: Authentication uses HttpOnly session cookies set by the
// backend. The browser sends them automatically on every request (via
// withCredentials: true). The csrf_token cookie is non-HttpOnly so JS can
// read it and attach it as the X-CSRF-Token header on mutating requests.
// This eliminates the XSS token-theft attack surface that existed with
// sessionStorage-based JWT management.

apiClient.interceptors.request.use((config) => {
  const method = (config.method ?? '').toLowerCase()
  if (CSRF_METHODS.has(method)) {
    const csrfToken = getCsrfToken()
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
  }
  return config
})

// ── Response interceptor: 401 redirect + error passthrough ──

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<{ error?: string; success?: boolean }>) => {
    if (error.response?.status === 401 && !IS_DEV_AUTH_BYPASS) {
      // The server clears the session cookie via Set-Cookie: Max-Age=0.
      // We only need to sync the Zustand auth state.
      import('@/stores/auth').then(({ useAuthStore }) => {
        useAuthStore.getState().handleUnauthorized()
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
