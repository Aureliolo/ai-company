/**
 * CSRF token utilities.
 *
 * The backend sets a non-HttpOnly `csrf_token` cookie on login/setup.
 * All mutating requests (POST/PUT/PATCH/DELETE) must include an
 * `X-CSRF-Token` header whose value matches this cookie.
 */

import { createLogger } from '@/lib/logger'

const log = createLogger('csrf')

/**
 * Read the CSRF token from the non-HttpOnly csrf_token cookie.
 *
 * Returns null when the cookie is absent (e.g. before login or after
 * cookie expiry).
 */
export function getCsrfToken(): string | null {
  const match = document.cookie
    .split(';')
    .map((s) => s.trim())
    .find((row) => row.startsWith('csrf_token='))
  if (!match) return null
  const eqIdx = match.indexOf('=')
  if (eqIdx === -1) return null
  try {
    return decodeURIComponent(match.slice(eqIdx + 1))
  } catch (err) {
    // Malformed cookie encoding -- log for diagnosis, return null
    // so the CSRF interceptor omits the header (server returns 403).
    log.warn('Failed to decode csrf_token cookie:', err)
    return null
  }
}
