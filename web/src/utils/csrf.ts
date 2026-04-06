/**
 * CSRF token utilities.
 *
 * The backend sets a non-HttpOnly `csrf_token` cookie on login/setup.
 * All mutating requests (POST/PUT/PATCH/DELETE) must include an
 * `X-CSRF-Token` header whose value matches this cookie.
 */

/**
 * Read the CSRF token from the non-HttpOnly csrf_token cookie.
 *
 * Returns null when the cookie is absent (e.g. before login or after
 * cookie expiry).
 */
export function getCsrfToken(): string | null {
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrf_token='))
  return match ? decodeURIComponent(match.split('=')[1]!) : null
}
