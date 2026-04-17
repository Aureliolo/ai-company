/**
 * Locale source of truth for the dashboard.
 *
 * Parallel to `@/utils/currencies` -- export a fallback constant plus a
 * runtime reader that resolves, in precedence order:
 *
 *   1. The user / company override from `useSettingsStore().locale`,
 *      sourced from the `display.locale` backend setting.
 *   2. The browser's language tag (`navigator.language`), so a user
 *      in Zurich lands on `de-CH` and a user in Paris lands on
 *      `fr-FR` without any configuration.
 *   3. {@link APP_LOCALE_FALLBACK} (`'en'`), a neutral language-only
 *      tag used only when no browser tag is available (SSR, unit
 *      tests) and no override is configured.
 *
 * Every formatter helper in `@/utils/format` accepts an optional
 * `locale?: string` parameter and falls back to `getLocale()` when
 * not provided.
 */

import { useSettingsStore } from '@/stores/settings'

/**
 * Last-resort fallback BCP 47 tag. Plain `'en'` is deliberate: it
 * avoids privileging a specific region (US date order, imperial
 * units, etc.) when no browser or operator signal is available. `Intl`
 * picks locale-appropriate defaults from the language subtag alone.
 */
export const APP_LOCALE_FALLBACK = 'en'

/**
 * Backwards-compatible alias for {@link APP_LOCALE_FALLBACK}.
 *
 * @deprecated Prefer {@link getLocale} so runtime resolution
 * (settings override, then browser locale) is applied. Kept as an
 * exported name because existing tests import `APP_LOCALE` to assert
 * the fallback-shape contract.
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

function readSettingsOverride(): string | null {
  // Guard against calls during store hydration (the Zustand store is
  // created at module load but only populated after `fetchLocale()`).
  try {
    const raw = useSettingsStore.getState().locale
    if (typeof raw !== 'string') return null
    const trimmed = raw.trim()
    if (trimmed.length === 0) return null
    Intl.getCanonicalLocales(trimmed)
    return trimmed
  } catch {
    return null
  }
}

/**
 * Return the active locale for display formatting.
 *
 * Resolution order: settings-store override (from `display.locale`)
 * -> browser language -> {@link APP_LOCALE_FALLBACK}. Centralizing
 * this lookup means every formatter helper picks up a new user
 * preference the moment the store updates.
 */
export function getLocale(): string {
  return readSettingsOverride() ?? readBrowserLocale() ?? APP_LOCALE_FALLBACK
}
