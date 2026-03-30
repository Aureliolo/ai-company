/**
 * Read the CSP nonce from a {@link HTMLMetaElement `<meta name="csp-nonce">`} tag.
 *
 * The nonce is expected to be injected into `index.html` by the serving
 * infrastructure (e.g. nginx `sub_filter`). If no meta tag is present
 * (local dev, environments without CSP nonce injection), returns `undefined`.
 *
 * The value is read once and cached for the lifetime of the page.
 */

let cached: string | undefined

export function getCspNonce(): string | undefined {
  if (cached !== undefined) return cached

  const meta = document.querySelector<HTMLMetaElement>(
    'meta[name="csp-nonce"]',
  )
  cached = meta?.content || undefined
  return cached
}
