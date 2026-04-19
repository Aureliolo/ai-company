# Web HTTP Adapter -- Evaluation and Decision

> **Spec topic**: web dashboard HTTP layer.
>
> **Status**: 2026-04-19. Closes #1467 (evaluated, no change). Feeds the
> ratchet-down plan tracked by #1466 and the follow-up "reach 0 leaks"
> issue filed alongside this PR.
>
> **Decision (TL;DR)**: keep `axios` (XHR adapter) in production and in
> tests. Accept a **structural ceiling of 50 async leaks** in the Vitest
> suite and enforce it with a CI gate. The remaining 50 leaks are inside
> MSW 2.x's own interceptor stack and cannot be eliminated without
> replacing MSW itself, which would regress PR #1462's Storybook +
> typed-handler ergonomics that just landed.

## Why this document exists

Issue #1467 asked whether we should flip `axios`'s adapter from the
default `XMLHttpRequest` adapter to the `fetch` adapter in production.
The motivation came from #1466: Vitest's `--detect-async-leaks` reports
a large Promise-leak count in the Vitest suite, and the prevailing
hypothesis was that the XHR path was the source.

We ran the full behavioral audit and measured every feasible path
during the 2026-04-19 investigation. The findings contradict the
initial hypothesis: axios is **not** the root cause, so flipping its
adapter does not help. The note that follows documents what we
measured, why it matters, and what the ratchet-down plan must look
like going forward.

## What "async leaks" actually are

Vitest 4.x's `--detect-async-leaks` flag installs a Node
`async_hooks.createHook` that tracks every Promise created during a
test file (and every Promise triggered from one). At end of file it
collects Promises whose `promiseResolve` hook never fired -- i.e.
that never settled from Node's point of view. Those are reported as
`N × PROMISE leaking in <file>`.

The distinction is important: **settled Promises do not leak**,
even if no caller ever awaited them. A leak is a Promise that stays
pending forever. The stacks Vitest prints for each leak are the
Promise's *creation* stack, not the stack at detection time.

## The investigation

Every measurement below ran
`npm --prefix web run test -- --coverage --detect-async-leaks` on
the `test/web-test-leaks-fetch-eval` branch. Each path was tested in
isolation (or in a short-lived experiment worktree) so the numbers
are directly comparable.

| # | Approach | Leaks | Tests pass | Notes |
|---|---|---:|---:|---|
| 0 | Main branch (baseline) | 69 | 2592 / 2592 | Status quo. |
| 1 | A1 -- sync `document.cookie` shim on `Document.prototype` in `test-setup.tsx` | **50** | 2592 / 2592 | **Shipped.** 28% reduction. Eliminates all 17 `getCsrfToken`/`getAllDocumentCookies`-path tough-cookie leaks. |
| 2 | A1 + A3 -- monkey-patch `XMLHttpRequest.prototype.send` to track pending XHRs, abort them in `afterEach` + microtask drain | 50 | 2592 / 2592 | 0 delta. The leaks are from *completed* XHRs; draining the live set does not reach them. |
| 3 | A1 + A5 -- microtask/`setImmediate` drain in `afterEach` | 50 | 2592 / 2592 | 0 delta. Leaks survive `Promise.resolve(setImmediate)` collection. |
| 4 | Phase B -- replace jsdom with happy-dom (`vitest.config.ts` `environment: 'happy-dom'` + `npm install happy-dom`) | 67 | 2582 / 2592 (10 fail) | **Worse.** happy-dom introduces a new leak category via `FetchBodyUtility.toReadableStream` and does not remove MSW's XHR-interceptor path. |
| 5 | Phase C -- `apiClient.defaults.adapter = 'fetch'` + `apiClient.defaults.baseURL = 'http://localhost:3000/api/v1'` in `test-setup.tsx` | 146 | 2577 / 2592 (15 fail) | **Much worse.** MSW's fetch interceptor (`InterceptorHttpNetworkFrame.resolve`, `Object.respondWith`, `HttpHandler.cloneRequestOrGetFromCache`, `CookieStore.getCookies` via tough-cookie) generates more Promise chains than its XHR interceptor. |

Only approach #1 improved over the baseline. Approaches #4 and #5
made things strictly worse. Approaches #2 and #3 had no effect.

## Why none of the other paths work

The remaining 50 leaks after A1 fall into three categories (counts
from the post-A1 measurement):

1. **alpha-residual (1 leak)**: MSW 2.x's own
   `CookieStore.getCookies` (`node_modules/msw/lib/core/utils/cookieStore.mjs`)
   using `tough-cookie.getCookiesSync`, which internally allocates a
   Promise via `createPromiseCallback` even in the sync variant. MSW
   maintains its own cookie jar separate from `document.cookie`, so
   the `test-setup.tsx` shim cannot reach it.
2. **beta (32 leaks)**: MSW's XHR interceptor
   (`@mswjs/interceptors/lib/node/XMLHttpRequest-C8dIZpds.mjs:320:7` --
   `queueMicrotask(() => onRequest?.call(...).finally(...))` and a
   sibling at `:315:42` cloning `fetchRequest`). These Promises are
   created *during* axios's `xhr.send()` call inside the test body.
   The microtask callback settles and the outer Promise resolves, but
   the finalizer chain runs an emitter that itself `await`s
   `emitAsPromise`, which through `InterceptorSource.queue` binds to
   MSW's internal async frame. When the test body returns, the frame
   is still pending from `async_hooks`'s POV.
3. **gamma (17 leaks)**: axios's own internal chain at
   `axios/lib/core/Axios.js:196:27` -- `promise = promise.then(chain[i++], chain[i++])`
   builds a Promise chain per request. The outermost `.then()` in
   this chain is `init`'d during the test but only `promiseResolve`s
   when the full MSW interceptor chain has fully settled -- which,
   per category 2, it has not.

Replacing axios with a native-fetch client (ky / ofetch / bespoke)
would remove category 3 but would move categories 1+2 onto MSW's
*fetch* interceptor path, which we measured as 146 leaks in Phase C.
Net: worse. Replacing jsdom with happy-dom (Phase B) does not touch
MSW at all and introduces a separate happy-dom-specific leak
category. Net: worse.

The only path to 0 that the investigation identified is **replacing
MSW 2.x** with a mock layer that does not use
`@mswjs/interceptors` -- e.g. `nock` (intercepts at `http.request`)
or plain axios adapter mocks. That is rejected as out-of-scope: PR
#1462 just landed the MSW migration and it is load-bearing for
Storybook (`msw-storybook-addon`) and for the typed handler helpers
(`successFor<typeof endpoint>`, `paginatedFor<typeof endpoint>`,
per-domain `buildEntity()` builders) that give us compile-time drift
detection against the endpoint modules.

## Behavioral audit (for the prod adapter question)

Even though the adapter flip does not help tests, #1467 also asked
whether we should move to the fetch adapter in production for other
reasons (bundle size, modernization). The audit below documents the
features we depend on; every row stayed green on XHR.

| Dimension | axios XHR (current prod) | axios fetch (evaluated) | Verdict |
|---|---|---|---|
| `responseType: 'blob'` | Works (`src/api/endpoints/artifacts.ts:30`) | axios 1.15.0 fetch adapter does support `responseType`, but the conversion path is different; untested against our `downloadArtifactContent` shape | No change needed |
| `responseType: 'text'` | Works (`artifacts.ts:38`) | Same as above | No change needed |
| `withCredentials: true` | Works (`src/api/client.ts:52`). Cookies attached automatically. | `credentials: 'include'` equivalent; cookie handling differs between browsers and jsdom but is identical in prod browsers | No behavioral delta in prod |
| `timeout: 30_000` | `xhr.timeout` (wire time) | `AbortSignal.timeout` (wall-clock from request start) | Prod-browser behavior equivalent |
| 429 retry + `Retry-After` + `_rateLimitRetries` (`client.ts:123-188`) | Works. Config mutation survives axios's recursive `apiClient.request(retryConfig)` | Fetch adapter clones config differently; would need `WeakMap<InternalAxiosRequestConfig, number>` refactor to be safe | Non-trivial refactor required |
| CSRF interceptor (`client.ts:110-119`) | Works | Same; headers attachment is adapter-agnostic | No change |
| 401 handler (`client.ts:128-140`) | Works | Same | No change |
| `ApiResponse` / `PaginatedResponse` envelope unwrap (`client.ts:208-269`) | Works | Same; response.data shape is adapter-agnostic | No change |
| `signal: AbortController` | Works | Works | No change |
| SSE / streaming (`src/api/endpoints/providers.ts:162-237`) | Already uses native `fetch` directly, bypassing axios | Unchanged | Adapter-agnostic |
| `onUploadProgress` / `onDownloadProgress` | Not used anywhere | Fetch adapter does not support upload progress | N/A |
| `FormData` / `File` / `Blob` bodies | Not used | Both adapters support natively | N/A |
| `paramsSerializer`, `maxContentLength`, `decompress` | Not configured | Same | No change |
| `err.request` introspection | Not used in app or tests | Fetch adapter does not set `response.request` | No change |
| Bundle size | XHR adapter is already tree-shaken into `vendor-state` chunk (~5KB gzipped contribution) | Fetch adapter similar size | Not a forcing factor |
| Browser support | All modern (no IE11 constraint) | All modern | Equivalent |
| MSW interception | Via `@mswjs/interceptors/XMLHttpRequest` (measured 50 leaks) | Via `@mswjs/interceptors/fetch` (measured 146 leaks) | XHR path strictly better for leak count |

**Verdict**: there is no operational reason to move prod to the
fetch adapter. The fetch adapter would require the `_rateLimitRetries`
WeakMap refactor to keep the retry path safe, and MSW-leak behavior
in tests would get worse, not better. Staying on XHR is the
best-in-class choice for this stack as of 2026-04-19.

## What ships in this PR

1. `web/src/test-setup.tsx` -- A1 cookie shim (already landed).
2. `.github/workflows/ci.yml` -- `MAX_ASYNC_LEAKS` ceiling ratcheted
   from 69 to 50; strict parser fails the job if Vitest's
   `Leaks N leaks` summary line is missing (format-drift guard).
3. `docs/design/web-http-adapter.md` (this file).
4. Follow-up issue filed: "Replace MSW 2.x to reach 0 Vitest async
   leaks". Scope, acceptance criteria, and rejection of the lighter
   alternatives documented there.

## What does NOT ship (by design)

- No change to axios adapter in prod or tests. Keeps #1467 closed as
  "evaluated, no change".
- No jsdom -> happy-dom swap. Measured as worse.
- No MSW replacement. Out of scope; load-bearing for Storybook.
- No axios replacement. Measured as worse via the Phase C proxy
  (which uses the same MSW fetch interceptor that a native-fetch
  client would).

## References

- #1466 -- original "eliminate async leaks" issue.
- #1467 -- "evaluate switching axios XHR adapter to fetch" (closed by
  this note).
- PR #1462 -- MSW migration that gave us typed handlers and raised
  the leak count from 69 to ~85 (since ratcheted to 69, now 50).
- `web/CLAUDE.md` -- MSW handlers contract and test teardown
  requirements that this PR preserves.
