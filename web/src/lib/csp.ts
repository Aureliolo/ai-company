/**
 * Read the CSP nonce from a {@link HTMLMetaElement `<meta name="csp-nonce">`} tag.
 *
 * The nonce is expected to be injected into `index.html` by the serving
 * infrastructure (e.g. nginx `sub_filter`). If no meta tag is present
 * (local dev, environments without CSP nonce injection), returns `undefined`.
 *
 * The value is read once on first call and cached for the lifetime of the
 * page -- both present and absent results are cached.
 */

const UNREAD: unique symbol = Symbol('unread')
let cached: string | undefined | typeof UNREAD = UNREAD

export function getCspNonce(): string | undefined {
  if (cached !== UNREAD) return cached as string | undefined

  const meta = document.querySelector<HTMLMetaElement>(
    'meta[name="csp-nonce"]',
  )
  cached = meta?.content?.trim() || undefined
  return cached
}
