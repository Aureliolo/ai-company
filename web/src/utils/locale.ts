/**
 * Locale source of truth for the dashboard.
 *
 * Parallel to `@/utils/currencies` -- export a default constant plus a
 * runtime reader that can later resolve a per-user or per-company locale
 * override from the settings store. Every formatter helper in
 * `@/utils/format` accepts an optional `locale?: string` parameter and
 * falls back to `getLocale()` when not provided.
 */

/** IETF BCP 47 default locale. */
export const APP_LOCALE = 'en-US'

/**
 * Return the active locale for display formatting.
 *
 * Currently always returns `APP_LOCALE`. The function exists as the
 * central hook so the settings store can swap in a user-selected locale
 * once the backend exposes a `display.locale` setting without churning
 * every callsite.
 */
export function getLocale(): string {
  return APP_LOCALE
}
