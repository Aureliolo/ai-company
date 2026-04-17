/**
 * Locale source of truth for the dashboard.
 *
 * Parallel to `@/utils/currencies` -- export a fallback constant plus a
 * runtime reader that resolves, in precedence order:
 *
 *   1. A user / company override (wired in a later change once the
 *      settings store exposes a ``display.locale`` setting).
 *   2. The browser's language tag (``navigator.language``), so a user
 *      in Zurich lands on ``de-CH`` and a user in Paris lands on
 *      ``fr-FR`` without any configuration.
 *   3. {@link APP_LOCALE_FALLBACK} (``en-US``), used only when no
 *      browser tag is available (e.g. SSR, non-browser tests).
 *
 * Every formatter helper in `@/utils/format` accepts an optional
 * `locale?: string` parameter and falls back to `getLocale()` when
 * not provided.
 */

/**
 * Last-resort fallback BCP 47 tag. Applied only when the browser
 * does not expose ``navigator.language`` (SSR, unit tests) and no
 * user/company override is configured. Consumers should prefer
 * {@link getLocale} over this constant so the runtime resolution
 * wins at every callsite.
 */
export const APP_LOCALE_FALLBACK = 'en-US'

/**
 * Backwards-compatible alias for {@link APP_LOCALE_FALLBACK}.
 *
 * @deprecated Prefer {@link getLocale} so runtime resolution (browser
 * locale, then user override) is applied. Kept as an exported name
 * because existing tests import ``APP_LOCALE`` to assert the
 * fallback-shape contract.
 */
export const APP_LOCALE = APP_LOCALE_FALLBACK

function readBrowserLocale(): string | null {
  if (typeof navigator === 'undefined') return null
  const raw = navigator.language
  if (typeof raw !== 'string' || raw.length === 0) return null
  try {
    Intl.getCanonicalLocales(raw)
    return raw
  } catch {
    return null
  }
}

/**
 * Return the active locale for display formatting.
 *
 * Resolution order: user/company override (not yet wired) →
 * browser language → {@link APP_LOCALE_FALLBACK}. Centralizing this
 * lookup means we can plug in a settings-store reader later without
 * churning every callsite.
 */
export function getLocale(): string {
  // TODO(settings-store): consult the company/user override first
  // once the backend exposes a ``display.locale`` setting.
  return readBrowserLocale() ?? APP_LOCALE_FALLBACK
}
