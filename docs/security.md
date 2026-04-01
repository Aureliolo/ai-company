---
title: Security
description: Security architecture, hardening measures, and compliance posture of the SynthOrg framework.
---

# Security

SynthOrg is designed to run autonomous AI agents with real tools and real consequences.
Security is not an afterthought -- it is a core architectural concern woven through
every layer of the framework, from the application runtime to the CI/CD pipeline
and container infrastructure.

---

## Application Security

### SecOps Agent & Rule Engine

Every tool invocation passes through a centralized security evaluation pipeline
before execution. The **SecOps service** coordinates a fail-closed rule engine
with five built-in detectors:

| Detector | What It Catches |
|----------|----------------|
| **Policy Validator** | Action type policies (soft-allow / hard-deny / escalate) |
| **Credential Detector** | API keys, passwords, tokens, private keys in arguments or output |
| **Path Traversal Detector** | `../`, absolute paths, symlink escape attempts |
| **Destructive Operation Detector** | `rm -rf`, `git reset --hard`, destructive shell commands |
| **Data Leak Detector** | PII patterns -- emails, SSNs, credit card numbers, phone numbers |

Rules are evaluated sequentially by priority. The first `DENY` or `ESCALATE`
verdict wins. If a rule raises an exception, the engine defaults to **DENY**
(fail-closed). Every decision is recorded in a persistent audit log.

### Output Scanning

After tool execution, the **output scanner** inspects results for sensitive data
using the same credential and PII patterns. Configurable response policies:

- **Redact** -- replace matches with `[REDACTED]` before returning to the agent
- **Withhold** -- suppress the entire output
- **Log-only** -- record the finding, return unmodified output
- **Autonomy-tiered** -- different policies per autonomy level

### Progressive Trust

Agents start with restricted permissions and earn autonomy over time.
Four pluggable strategies behind the `TrustStrategy` protocol:

1. **Disabled** -- all actions require approval regardless of history
2. **Weighted** -- accumulate a trust score from successful actions
3. **Per-category** -- independent trust tracks per action type (read, write, delete)
4. **Milestone gates** -- unlock action categories after specific success thresholds

### Approval Workflow

Actions that trigger `ESCALATE` verdicts create approval items with configurable
timeout policies:

- **Wait forever** -- block until a human responds
- **Auto-deny** -- reject after timeout
- **Tiered** -- different timeouts by risk level
- **Escalation chain** -- escalate to supervisor on timeout

Tasks are parked (suspended) while awaiting approval and resumed automatically
on resolution.

### Authentication & Authorization

- **JWT bearer tokens** with password-change detection (`pwd_sig` claim, skipped for system user)
- **System user (CLI)** -- internal identity bootstrapped at startup with a random Argon2id password hash. CLI tokens use `sub: "system"` with `iss: "synthorg-cli"` and skip `pwd_sig` validation (JWT HMAC signature is the sole authentication gate). The system user cannot log in, change its password, or be modified through the API.
- **API key authentication** via HMAC-SHA256 deterministic hashing
- **Argon2id password hashing** (time_cost=3, memory_cost=64 MB, parallelism=4)
- **Timing-attack prevention** -- dummy hash computation for non-existent users
- **Forced password change** -- `must_change_password` flag blocks API access
- **One-time WebSocket tickets** -- short-lived (30 s), single-use, cryptographically random tokens exchanged via ``POST /api/v1/auth/ws-ticket`` (requires valid JWT). Prevents long-lived JWT leakage by replacing it with an ephemeral ticket in the WebSocket query parameter. In-memory store, monotonic clock expiry, per-process scope. JWT/API key auth middleware is scoped to HTTP requests only (`ScopeType.HTTP`) -- WebSocket connections bypass the middleware entirely and rely on handler-level ticket validation.
- **Rate limiting** -- configurable per-deployment (default: 100 req/min). The WebSocket path is excluded from rate limiting -- HTTP-style per-request rate limiting is inappropriate for persistent WebSocket connections. Auth-sensitive endpoints (``/auth/login``, ``/auth/setup``, ``/auth/change-password``) have a stricter route-level rate limit of 10 req/min to mitigate credential brute-forcing.

### Frontend Security

The React dashboard enforces several measures to reduce the client-side attack
surface:

| Measure | Mechanism |
|---------|-----------|
| **XSS prevention** | ESLint `no-restricted-syntax` rule bans `dangerouslySetInnerHTML` at write time. Override requires `// eslint-disable-next-line` with justification. |
| **CSP nonce readiness** | `<MotionConfig nonce>` wrapper in `App.tsx` + `lib/csp.ts` reader. Framer Motion's dynamically injected `<style>` tags are nonce-ready. `react-style-singleton` (used by Radix Dialog/AlertDialog/Popover via `react-remove-scroll`) also supports nonces via the `get-nonce` package -- wiring `setNonce()` in `lib/csp.ts` is the remaining step. Currently staged -- see the activation checklist in `web/index.html` and the [accepted risk](#accepted-risk-inline-style-attributes) section below. |
| **JWT storage** | `localStorage` with short-lived tokens, automatic expiry cleanup, and 401 interceptor. Cookie-based auth (httpOnly) is a future enhancement tracked separately. |

### Accepted Risk: Inline Style Attributes

The dashboard CSP includes `style-src 'unsafe-inline'` because Radix UI primitives inject
inline styles at runtime. This section documents the risk, the upstream blocker, and the
recommended mitigation path.

#### What is permitted

Under CSP Level 2, `style-src 'unsafe-inline'` allows all inline styles -- both `style`
attributes on DOM elements and `<style>` elements without nonces. With CSP Level 3 directive
splitting, `style-src-attr 'unsafe-inline'` permits only inline `style` attributes while
`style-src-elem` controls `<style>` elements separately (e.g. via nonces or hashes).

#### Why this is required

Radix UI primitives violate CSP in two distinct ways:

1. **Inline `style` attributes on DOM elements.** Radix Popper (used by Popover, Tooltip,
   Select, DropdownMenu) sets CSS custom properties via `style="--radix-*: ..."`.
   Dialog/AlertDialog set `style="pointer-events: auto"` on overlays. Tabs set
   `animationDuration: "0s"` on mount. **CSP nonces cannot fix this** -- the CSP
   specification only supports nonces on `<style>` and `<script>` elements, not on
   `style` attributes.

2. **`<style>` tag injection.** `react-remove-scroll` / `react-style-singleton` (used by
   Dialog, AlertDialog, Popover) inject `<style>` tags at runtime. **This is fixable** --
   `react-style-singleton` already calls `getNonce()` from the `get-nonce` package and
   applies nonces to its `<style>` tags when `setNonce()` has been called.

**Affected dashboard components:** Dialog (4 pages), AlertDialog/ConfirmDialog (1),
Popover/ThemeToggle (1), Tabs/OrgEditPage (1), FocusScope/CommandPalette (1). Additionally,
`cmdk` (CommandPalette) internally depends on `@radix-ui/react-dialog`.

#### Risk assessment

Inline `style` attribute injection is **not a practical XSS vector**:

- Unlike `<script>` or `<style>` elements, a `style` attribute **cannot execute JavaScript**
- Data exfiltration via `style` attributes is limited to single-element visual manipulation
  (no CSS selectors and no `@import`; `url(...)` loading is possible but constrained by
  relevant CSP fetch directives such as `img-src` and `font-src`)
- The primary theoretical risk is UI redress/clickjacking via
  `position: fixed; z-index: 99999`, which is already mitigated by `X-Frame-Options: DENY`
- The higher-risk vector (`<style>` element injection for CSS-based data exfiltration via
  attribute selectors) is separately addressable via nonces

`script-src` -- the critical XSS vector -- is locked down to `'self'` with no `'unsafe-inline'`.

#### Upstream status (stagnant)

| Date | Event |
|------|-------|
| 2024-02 | Nonce prop merged for ScrollArea/Select only ([PR #2728](https://github.com/radix-ui/primitives/pull/2728)) |
| 2024-09 | CSS export approach PR closed by maintainer (backlog triage, [PR #3131](https://github.com/radix-ui/primitives/pull/3131)) |
| 2024-10 | Maintainer said "near the top of my todo list" |
| 2025-04 | Community asked for update -- no response |
| 2025-07 | Community followed up -- no response |
| 2026-01 | Community re-opened inquiry -- no response |
| 2026-02 | [Discussion #3130](https://github.com/radix-ui/primitives/discussions/3130) **closed** -- author pointed to Base UI as the successor with CSP support |

Open issues with no maintainer engagement:
[#3063](https://github.com/radix-ui/primitives/issues/3063),
[#3117](https://github.com/radix-ui/primitives/issues/3117).

#### Base UI migration assessment

[Base UI 1.0](https://base-ui.com) (released December 2025, currently v1.3.0) offers first-class
CSP support via [`CSPProvider`](https://base-ui.com/react/utils/csp-provider) with context-based
nonce propagation. However, migrating is **prohibitively large**:

- The dashboard has 9 direct Radix imports across the codebase
- shadcn/ui is architecturally built on Radix primitives -- migrating away from Radix means
  replacing the entire component system in `web/src/components/ui/`
- `cmdk` (CommandPalette) depends on `@radix-ui/react-dialog` internally -- no Base UI
  equivalent exists
- Base UI's `CSPProvider` solves `<style>` element injection but would **still likely require
  `style-src-attr 'unsafe-inline'`** for positioned components that use inline `style`
  attributes (Floating UI, which Base UI also uses, sets inline styles for positioning)

**Verdict:** the migration scope is disproportionate to the marginal security gain beyond what
nonce wiring + directive splitting already achieves.

#### Recommended mitigation path

**Phase 1 -- Wire `get-nonce` bridge** (low effort, high impact):
Add a `setNonce()` call from the `get-nonce` package in `web/src/lib/csp.ts` so that
`react-style-singleton`'s `<style>` tags receive the CSP nonce. Combined with the existing
`MotionConfig nonce` wrapper, this makes all `<style>` element injection nonce-capable.

**Phase 2 -- Activate nonce infrastructure + split CSP directives** (coordinated deployment):
Uncomment the `<meta name="csp-nonce">` tag in `web/index.html`, add `sub_filter` to
`web/nginx.conf`, and replace `style-src 'self' 'unsafe-inline'` with CSP Level 3 split
directives in `web/security-headers.conf`:

- `style-src-elem 'self' 'nonce-...'` -- locks down `<style>` elements (higher-risk vector)
- `style-src-attr 'unsafe-inline'` -- permits inline `style` attributes (low-risk, required
  by Radix)

Browser support for CSP Level 3 directive splitting:

- `style-src-elem`: Chrome 75+, Firefox 108+, Safari 15.4+ (partial, full at 26.2+), Edge 79+
- `style-src-attr`: Chrome 75+, Edge 79+. **Not supported** in Firefox
  ([bug 1529338](https://bugzilla.mozilla.org/show_bug.cgi?id=1529338)) or Safari

When `style-src-attr` is unsupported, browsers fall back to `style-src`, so the directive
splitting is backwards-compatible -- unsupported browsers continue using `style-src` rules.

**Phase 3 -- Re-evaluate quarterly:**
Check upstream Radix issues ([#3063](https://github.com/radix-ui/primitives/issues/3063),
[#3117](https://github.com/radix-ui/primitives/issues/3117)) for movement. If Radix ships
nonce support for inline styles, or if Base UI reaches feature parity with the dashboard's
Radix usage, remove `style-src-attr 'unsafe-inline'`.

### Security Headers

All API responses include:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=()` |
| `Cross-Origin-Resource-Policy` | `same-origin` |
| `Cross-Origin-Opener-Policy` | `same-origin` (API); `same-origin-allow-popups` (docs) |
| `Cache-Control` | `no-store` (API); `no-cache` (dashboard HTML); `public, max-age=31536000, immutable` (dashboard hashed assets); `public, max-age=300` (docs) |
| `Content-Security-Policy` | Strict default; relaxed only for docs UI. Dashboard requires `style-src 'unsafe-inline'` due to Radix UI inline style injection ([accepted risk](#accepted-risk-inline-style-attributes)). Nonce infrastructure is staged for `<style>` elements (Framer Motion + react-style-singleton); full activation blocked by Radix inline `style` attributes. See recommended mitigation path for CSP Level 3 directive splitting. |

---

## Container Hardening

### Distroless Runtime

The backend runs on a **Chainguard distroless Python image** -- no shell,
no package manager, minimal attack surface. The build uses a 3-stage
Dockerfile:

1. **Builder** -- compiles dependencies and project wheel
2. **Setup** -- fixes paths and creates directories (dev image with shell)
3. **Runtime** -- distroless production image (no shell, UID 65532)

### CIS Docker Benchmark

Both backend and web containers enforce CIS v1.6.0 controls in `compose.yml`:

| Control | Setting |
|---------|---------|
| **CIS 5.3** | `security_opt: no-new-privileges:true` |
| **CIS 5.12** | `cap_drop: ALL` |
| **CIS 5.25** | `read_only: true` with `tmpfs` mounts (`noexec`, `nosuid`, `nodev`) |
| **CIS 5.28** | `deploy.resources.limits.pids` per container (256 backend, 64 web) |

Resource limits (`deploy.resources.limits`) cap memory, CPU, and PIDs per container (4G/2CPU/256pids backend, 256M/0.5CPU/64pids web). Log rotation (`json-file` driver, `max-size: 10m`, `max-file: 3`) prevents disk exhaustion.

### Artifact Provenance

- All base images **pinned by SHA-256 digest** (no mutable tags)
- **Dependabot** auto-updates digests daily for all three Dockerfiles
- **cosign keyless signing** on every pushed image (Sigstore OIDC-bound)
- **Buildx SPDX SBOMs** (SLSA L1) auto-generated and pushed to GHCR as registry attestations (inspect via `docker buildx imagetools inspect`). Standalone CycloneDX JSON SBOMs are generated separately by Syft -- see [Software Bill of Materials](#software-bill-of-materials-sbom) below.
- **Build-level provenance** (SLSA L1) auto-generated by Docker Buildx
- **SLSA Level 3 provenance** for CLI binary releases and container images (generated by `actions/attest-build-provenance`, Sigstore-signed, independently verifiable)
- **Client-side verification**: The CLI (`synthorg start`, `synthorg update`) automatically verifies cosign signatures and SLSA provenance for container images before pulling. Verified digests are pinned in the compose file to prevent tag mutation attacks. Bypass with `--skip-verify` or `SYNTHORG_SKIP_VERIFY=1` for air-gapped environments (not recommended).

---

## Supply Chain Security

### Dependency Management

| Layer | Tool | Policy |
|-------|------|--------|
| Python | `pip-audit` | Per-PR + weekly scan for known CVEs |
| Python | Dependabot | Daily updates, `==` pinned versions, grouped minor/patch |
| Node.js | `npm audit` | Per-PR, blocks on critical/high |
| Node.js | Dependabot | Daily updates via lockfile (`/web`, `/site`, `/.github`) |
| GitHub Actions | Dependabot | Daily updates, pinned by SHA |
| Pre-commit hooks | Dependabot | Daily updates, version-pinned `rev:` tags |
| License | `dependency-review-action` | Permissive-only allowlist (MIT, Apache-2.0, BSD, ISC, etc.) |
| Supply chain | Socket.dev | GitHub App -- detects typosquatting, malware, suspicious ownership changes |

### Container Scanning

Every container image is scanned by **two independent tools** before push:

- **Trivy** -- CRITICAL = hard fail, HIGH = warn-only (`.trivyignore.yaml` for vetted CVEs)
- **Grype** -- critical severity cutoff (`.grype.yaml` for overrides)
- **CIS Docker Benchmark** -- `trivy image --compliance docker-cis-1.6.0` run against all three images (informational; will become enforced once baseline is clean)

Images are **only pushed to GHCR after both vulnerability scanners pass**.

### Signed Artifacts

- **Container images**: cosign keyless signatures (verify via `cosign verify`) + SLSA Level 3 provenance attestations (verify via `gh attestation verify`)
- **CLI binaries**:
    - cosign keyless signature on checksums file (verify via `cosign verify-blob`)
    - SLSA Level 3 provenance attestations (verify via `gh attestation verify`)
    - Sigstore provenance bundle (`.sigstore.json`, verify via `cosign verify-blob-attestation`)
- **Git commits**: GPG/SSH signed (enforced by branch protection ruleset)
- **GitHub Actions**: All actions pinned by full SHA commit hash
- **GitHub Releases**: Immutable releases enabled -- once published, assets and body cannot be modified (prevents supply chain tampering). Releases are created as drafts by Release Please, finalized after all assets are attached.

### Software Bill of Materials (SBOM)

Every release includes CycloneDX JSON SBOMs for all released artifacts:

- **Container images**: per-image SBOMs (`sbom-backend.cdx.json`, `sbom-web.cdx.json`,
  `sbom-sandbox.cdx.json`) generated by [Syft](https://github.com/anchore/syft),
  attached to GitHub Releases as downloadable assets
- **CLI binaries**: per-archive SBOMs (e.g. `synthorg_linux_amd64.tar.gz.cdx.json`)
  generated by GoReleaser + Syft, attached to GitHub Releases
- **Registry attestations**: Buildx-generated SPDX SBOMs pushed to GHCR alongside
  each image (inspect via `docker buildx imagetools inspect`)

---

## CI/CD Security

### Pre-Commit Hooks

Every commit is checked locally before it reaches the remote:

- **gitleaks** -- secret detection on every commit
- **hadolint** -- Dockerfile linting
- **ruff** -- Python linting and formatting
- **commitizen** -- conventional commit message enforcement
- **Large file prevention** -- blocks files over 1 MB

Pre-push hooks run **mypy type checking** and **unit tests** as a fast gate.

### Continuous Integration

| Check | Gate |
|-------|------|
| Ruff lint + format | Required |
| mypy strict type-check | Required |
| pytest + 80% coverage | Required |
| pip-audit (Python CVEs) | Required |
| npm audit (Node.js CVEs) | Required |
| hadolint (Dockerfile lint) | Required |
| All checks must pass | `ci-pass` required status check |

### Security Scanning

| Scanner | Scope | Schedule |
|---------|-------|----------|
| **gitleaks** | Secret detection (push/PR + weekly) | Continuous |
| **CodeQL** | Static analysis (GitHub Advanced Security) | On push/PR |
| **zizmor** | GitHub Actions workflow security | On push/PR |
| **ZAP DAST** | Dynamic API scan against OpenAPI spec | On push to main + weekly |
| **OSSF Scorecard** | Supply chain maturity scoring | Weekly + on push |
| **Trivy + Grype** | Container vulnerability scanning | On image build |
| **Socket.dev** | Supply chain attack detection | On PR |
| **dependency-review** | License + vulnerability review | On PR |

### DAST Tuning

The ZAP API scan runs with a rules file (`.github/zap-rules.tsv`) that
suppresses validated false positives and informational findings:

| Rule | ID | Action | Rationale |
|------|----|--------|-----------|
| Unexpected Content-Type | 100001 | Ignore | `/docs` intentionally serves Scalar UI HTML |
| Client Error Responses | 100000 | Ignore | ZAP sends literal path params, expected 4xx |
| Base64 Disclosure | 10094 | Ignore | OpenAPI schema contains UUID/JWT-format refs, not secrets |
| Sec-Fetch-* Missing | 90005 | Ignore | JWT auth (not cookies) -- no CSRF risk, would break non-browser clients |
| Non-Storable Content | 10049 | Warn | API endpoints correctly use `no-store`; dashboard HTML uses `no-cache`; hashed assets use `immutable`; docs use `public, max-age=300` |

The rules file is reviewed when ZAP or the API surface changes.
Cache-Control is path-aware: API data endpoints use `no-store` to prevent
sensitive data caching, the web dashboard entry point (`index.html`) uses
`no-cache` to force revalidation on every request (ensuring fresh deployments),
content-hashed dashboard assets (`/assets/*`) use `public, max-age=31536000,
immutable` for long-lived caching, and documentation endpoints (`/docs/*`)
allow brief client and proxy caching since they serve public, non-user-specific
content.

### Branch Protection

The `protect-main` ruleset enforces:

- **Signed commits** required
- **No direct pushes** -- all changes via pull request
- **1 approving review** required (stale reviews dismissed on push)
- **`ci-pass` status check** required before merge
- **No branch deletion** or non-fast-forward pushes

---

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly via
[GitHub Security Advisories](https://github.com/Aureliolo/synthorg/security/advisories/new).
Do not open a public issue for security vulnerabilities.
