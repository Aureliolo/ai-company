import { createLogger } from '@/lib/logger'

const log = createLogger('csp')

const UNREAD: unique symbol = Symbol('unread')
let cached: string | undefined | typeof UNREAD = UNREAD

/**
 * Read the CSP nonce from the `<meta name="csp-nonce">` tag in `index.html`.
 *
 * The nonce is injected at serve time by nginx `sub_filter` (substituting
 * `__CSP_NONCE__` with the per-request `$request_id` value). At runtime,
 * this reader parses the meta tag and returns the nonce string, which is
 * passed to Base UI's `CSPProvider` and Framer Motion's `MotionConfig` so
 * every dynamically injected `<style>` element carries the nonce.
 *
 * See `docs/security.md#csp-nonce-infrastructure` for the full flow.
 *
 * The value is read once on first call and cached for the lifetime of the
 * page -- both present and absent results are cached. Missing or invalid
 * values are logged so deployment misconfigurations are visible:
 *
 * - In production, the literal `__CSP_NONCE__` placeholder reaching the
 *   client indicates nginx `sub_filter` is broken -- this is logged at
 *   ERROR level because the CSP will block every injected `<style>` tag.
 * - In the Vite dev server (`import.meta.env.DEV`), the placeholder is
 *   always present (nginx never runs), so the same condition is logged at
 *   DEBUG level to avoid false-positive noise on every local page load.
 *
 * **Threat model note:** The nonce is readable by all same-origin JavaScript,
 * so it does not prevent an attacker who has already achieved XSS from
 * reusing it. Its purpose is to permit Base UI and Framer Motion's
 * dynamically injected `<style>` tags under a CSP that forbids
 * `'unsafe-inline'` on `style-src-elem`. The nonce must be per-request and
 * unpredictable (nginx `sub_filter` substituting `$request_id`, a 128-bit
 * pseudo-random identifier) to prevent replay across requests.
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
    // Placeholder survived: in production this means nginx sub_filter is
    // misconfigured and the CSP will block every injected <style>. In the
    // Vite dev server the placeholder is always present because nginx never
    // runs, so downgrade to DEBUG to avoid false-positive error noise.
    if (import.meta.env.DEV) {
      log.debug('CSP nonce placeholder present (dev server)', {
        note: 'expected outside nginx; styles unsigned in dev',
      })
    } else {
      log.error('CSP nonce placeholder not substituted', {
        impact: 'nginx sub_filter is misconfigured -- CSP will block inline styles',
      })
    }
  } else if (!value) {
    log.warn('CSP nonce meta tag present but empty')
  }

  // Reject the un-substituted nginx placeholder: if __CSP_NONCE__ appears
  // literally, sub_filter is misconfigured (or we are in dev), and the
  // value is not a real nonce.
  cached = value && value !== '__CSP_NONCE__' ? value : undefined
  return cached
}
