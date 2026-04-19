# Vitest Async Leak Stacks -- Baseline and Per-Patch Deltas

**Temporary artifact.** This file feeds `docs/design/web-http-adapter.md`
(Phase D design note for #1467). It MUST be deleted before the PR is
opened -- the summary table lands in the design note verbatim.

## Source of truth

`npm --prefix web run test -- --coverage --detect-async-leaks` on branch
`test/web-test-leaks-fetch-eval` at the commit that opens PR. Vitest
already prints each leaked Promise's full stack via its `BaseReporter`
(`vitest/dist/chunks/index.BMXTnDNz.js`); leaks are deduplicated by
`relative(filename):line:column:type` before reporting.

No custom reporter is needed -- the default output is the evidence.

## Baseline -- 69 leaks, 2592 tests pass (2026-04-19)

Categorized by top-of-stack frame:

| Cat | Top frame | Count | Path into app code |
|---|---|---:|---|
| alpha | `createPromiseCallback` -> `CookieJar.getCookieString` (`tough-cookie/dist/index.cjs:209:19`) | 17 | Two paths: (a) our CSRF interceptor reading `document.cookie` in `src/api/client.ts:113` -> `src/utils/csrf.ts:20`; (b) MSW 2.x handler parsing reading cookies via `getAllDocumentCookies` in `msw/lib/core/utils/request/getRequestCookies.mjs`. |
| beta | `XMLHttpRequest.methodCall` (`@mswjs/interceptors/lib/node/XMLHttpRequest-C8dIZpds.mjs:320:7` -- `queueMicrotask(() => ...)` -- and a sibling at `:315:42` cloning `fetchRequest`) | 32 | Every axios XHR dispatch enters MSW's XHR interceptor, which schedules a microtask and clones the fetch-shaped request. The outer `new Promise` around that microtask is what Vitest's async_hooks sees as leaking when the test's awaited chain finishes before the microtask queue fully drains. |
| gamma | `Axios._request` (`axios/lib/core/Axios.js:196:27`, `promise = promise.then(chain[i++], chain[i++])`) | 18 | Every axios request builds a Promise chain from its interceptors + dispatch. When the final `.then()` is created but the adapter's underlying XHR queueMicrotask hasn't fired by test end, this outer chain shows up as pending. |
| epsilon | `new DeferredPromise` (`@open-draft/deferred-promise/build/index.mjs:38:5`) via `handleRequest` + `globalThis.fetch` | 1 | `src/utils/app-version.ts:121` (`callServerLogout`) uses **native fetch directly** (not axios). MSW's fetch interceptor wraps the call in a `DeferredPromise` that the test runner classifies as leaked. |
| zeta | unknown | 1 | Unaccounted for (69 total minus 68 categorized). Revisit during A-phase measurement. |

Total: 69.

## Patch hypotheses

| Patch | Closes category | Expected drop |
|---|---|---:|
| A1 -- synchronous `document.cookie` shim in `test-setup.tsx` | alpha (all 17) | 17 |
| A3 -- pending-XHR registry + abort in `afterEach` | beta (all 32) | 32 |
| A5 -- microtask drain (`queueMicrotask` x2) in `afterEach` | gamma (all 18) | 18 |
| Targeted -- await `callServerLogout` response.body drain in the test, OR rewrite the test to mock the fetch | epsilon (1) | 1 |
| (tbd) | zeta (1) | TBD |

Combined A1 + A3 + A5 expected reduction: **67 of 69**. Residual 2
expected after A-phase; those are addressed by targeted fixes
(epsilon, zeta) before the CI gate flips to hard 0.

## Per-patch measurement log (updated as patches land)

| Commit | Patch applied | Measured leaks | Delta | Notes |
|---|---|---:|---:|---|
| baseline (pre-A) | (none) | 69 | (none) | 2592 tests pass. |
| (uncommitted) | A1 -- cookie shim on `Document.prototype` | 50 | -19 | 2592 tests pass. Remaining: alpha=1, beta=32, gamma=15, epsilon=3. Note: attempting the shim on `document` (instance) broke `__tests__/utils/csrf.test.ts` which mocks `Document.prototype.cookie`; fix was to shim at the prototype level so the test's mocks layer on top and its `afterEach` captures the shim as "original". |
| (pending) | A3 -- XHR drain | _pending_ | _pending_ | Targets beta (32 leaks). |
| (pending) | A5 -- microtask drain | _pending_ | _pending_ | Targets gamma (15 leaks). |
| (pending) | targeted alpha (residual 1) + epsilon (3) | _pending_ | _pending_ | |
| (pending) | CI gate to 0 | _pending_ | _pending_ | Final commit. |

## Per-test-file distribution (baseline)

For triage and spot-checks. Derived by counting `PROMISE leaking in <file>`
lines in the baseline output.

- `src/__tests__/utils/app-version.test.ts`: 4
- `src/__tests__/stores/meetings.test.ts`: 4
- `src/__tests__/stores/auth.test.ts`: 4
- `src/__tests__/stores/tasks.test.ts`: 4
- `src/__tests__/stores/company.test.ts`: 4
- `src/__tests__/stores/projects.test.ts`: 4
- `src/__tests__/stores/sinks.test.ts`: 4
- `src/__tests__/stores/messages.test.ts`: 2
- `src/__tests__/stores/setup-wizard.test.ts`: 3
- `src/__tests__/stores/approvals.test.ts`: 3
- `src/__tests__/stores/websocket.test.ts`: 2
- `src/__tests__/stores/agents.test.ts`: 2
- `src/__tests__/router/guards.test.tsx`: 1 (spanning multiple lines)
- `src/__tests__/stores/budget.test.ts`: 2
- `src/__tests__/stores/analytics.test.ts`: 1
- `src/__tests__/pages/LoginPage.test.tsx`: 1
- `src/__tests__/stores/artifacts.test.ts`: 3
- `src/__tests__/stores/workflows.test.ts`: 3
- `src/__tests__/pages/TaskDetailPage.test.tsx`: 1
- `src/__tests__/components/layout/StatusBar.test.tsx`: 1
- `src/__tests__/stores/connections.test.ts`: 2
- `src/__tests__/hooks/useCommunicationEdges.test.ts`: 1
- `src/__tests__/stores/meta.test.ts`: 3
- `src/__tests__/stores/setup.test.ts`: 1
- `src/__tests__/stores/mcp-catalog.test.ts`: 3
- `src/__tests__/stores/subworkflows.test.ts`: 2
- `src/__tests__/App.test.tsx`: 1
- `src/__tests__/stores/tunnel.test.ts`: 2
- `src/__tests__/hooks/useTaskBoardData.test.ts`: 1

The file distribution is broad (~30 test files); no single test file
dominates. That reinforces that the fixes must be in `test-setup.tsx`
(shared teardown), not in individual tests.
