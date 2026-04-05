import { createLogger } from '@/lib/logger'

const log = createLogger('csp')

const UNREAD: unique symbol = Symbol('unread')
let cached: string | undefined | typeof UNREAD = UNREAD

/**
 * Read the CSP nonce from a {@link HTMLMetaElement `<meta name="csp-nonce">`} tag.
 *
 * The nonce is injected into `index.html` at serve time by nginx `sub_filter`
 * (substituting `__CSP_NONCE__` with the per-request `$request_id` value). At
 * runtime, this reader parses the meta tag and returns the nonce string, which
 * is then passed to Base UI's `CSPProvider` and Framer Motion's `MotionConfig`
 * so that every dynamically injected `<style>` element carries the nonce.
 *
 * See `docs/security.md` → CSP Nonce Infrastructure for the full flow.
 *
 * The value is read once on first call and cached for the lifetime of the
 * page -- both present and absent results are cached. Missing or placeholder
 * values are logged at WARNING level so that production misconfigurations
 * (e.g. nginx `sub_filter` not running) are visible in the browser console.
 *
 * **Threat model note:** The nonce is readable by all same-origin JavaScript,
 * so it does not prevent an attacker who has already achieved XSS from reusing
 * it. Its purpose is to permit Base UI and Framer Motion's dynamically
 * injected `<style>` tags under a CSP that forbids `'unsafe-inline'` on
 * `style-src-elem`. The nonce must be per-request and cryptographically
 * random (nginx `sub_filter` substituting `$request_id`) to prevent
 * pre-computation attacks.
 */
export function getCspNonce(): string | undefined {
  if (cached !== UNREAD) return cached

  const meta = document.querySelector<HTMLMetaElement>(
    'meta[name="csp-nonce"]',
  )
  const value = meta?.content?.trim()

  if (!meta) {
    // Missing meta tag: local dev without nginx in the path, or a
    // deployment misconfiguration. Inline <style> tags will be unsigned.
    log.warn('CSP nonce meta tag missing', {
      impact: 'inline <style> elements will not carry a nonce',
    })
  } else if (value === '__CSP_NONCE__') {
    // Placeholder survived: nginx sub_filter is misconfigured in production.
    log.error('CSP nonce placeholder not substituted', {
      impact: 'nginx sub_filter is misconfigured -- CSP will block inline styles',
    })
  } else if (!value) {
    log.warn('CSP nonce meta tag present but empty')
  }

  // Reject the un-substituted nginx placeholder -- if __CSP_NONCE__ appears
  // literally, sub_filter is misconfigured and the value is not a real nonce.
  cached = value && value !== '__CSP_NONCE__' ? value : undefined
  return cached
}
