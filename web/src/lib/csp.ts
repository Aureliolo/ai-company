const UNREAD: unique symbol = Symbol('unread')
let cached: string | undefined | typeof UNREAD = UNREAD

/**
 * Read the CSP nonce from a {@link HTMLMetaElement `<meta name="csp-nonce">`} tag.
 *
 * The nonce is expected to be injected into `index.html` by the serving
 * infrastructure (e.g. nginx `sub_filter`) once CSP nonce support is enabled.
 * Currently the meta tag is commented out in `index.html` -- see the activation
 * checklist there for the full setup steps. If no meta tag is present (local
 * dev, environments without CSP nonce injection), returns `undefined`.
 *
 * The value is read once on first call and cached for the lifetime of the
 * page -- both present and absent results are cached.
 *
 * **Threat model note:** The nonce is readable by all same-origin JavaScript,
 * so it does not prevent an attacker who has already achieved XSS from reusing
 * it. Its purpose is to permit Framer Motion's dynamically injected `<style>`
 * tags under a CSP that does not allow `'unsafe-inline'`. The nonce must be
 * per-request and cryptographically random (nginx `sub_filter`) to prevent
 * pre-computation attacks.
 */
export function getCspNonce(): string | undefined {
  if (cached !== UNREAD) return cached

  const meta = document.querySelector<HTMLMetaElement>(
    'meta[name="csp-nonce"]',
  )
  const value = meta?.content?.trim()

  // Reject the un-substituted nginx placeholder -- if __CSP_NONCE__ appears
  // literally, sub_filter is misconfigured and the value is not a real nonce.
  cached = value && value !== '__CSP_NONCE__' ? value : undefined
  return cached
}
