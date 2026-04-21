import { http, HttpResponse } from 'msw'
import { beforeEach } from 'vitest'
import type { SinkInfo, TestSinkResult } from '@/api/types/settings'
import { useSinksStore } from '@/stores/sinks'
import { useToastStore } from '@/stores/toast'
import { apiError, apiSuccess } from '@/mocks/handlers'
import { server } from '@/test-setup'

// Sinks-store-specific per-test state reset. Global afterEach in
// test-setup.tsx already clears toasts + notifications persistence,
// so we only reset the store itself here (and keep a defensive toast
// clear in case a prior test bypassed the global hook).
beforeEach(() => {
  useSinksStore.setState({ sinks: [], loading: false, error: null })
  useToastStore.getState().dismissAll()
})

function makeSink(overrides: Partial<SinkInfo> = {}): SinkInfo {
  return {
    identifier: '__console__',
    sink_type: 'console',
    level: 'INFO',
    json_format: false,
    rotation: null,
    is_default: true,
    enabled: true,
    routing_prefixes: [],
    ...overrides,
  }
}

beforeEach(() => {
  useSinksStore.setState({
    sinks: [],
    loading: false,
    error: null,
  })
})

describe('fetchSinks', () => {
  it('sets sinks on success', async () => {
    const sinks = [
      makeSink(),
      makeSink({ identifier: 'synthorg.log', sink_type: 'file' }),
    ]
    server.use(
      http.get('/api/v1/settings/observability/sinks', () =>
        HttpResponse.json(apiSuccess(sinks)),
      ),
    )

    await useSinksStore.getState().fetchSinks()

    const state = useSinksStore.getState()
    expect(state.sinks).toHaveLength(2)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('sets loading to true during fetch', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.get('/api/v1/settings/observability/sinks', async () => {
        await gate
        return HttpResponse.json(apiSuccess([makeSink()]))
      }),
    )

    const fetchPromise = useSinksStore.getState().fetchSinks()
    expect(useSinksStore.getState().loading).toBe(true)

    release()
    await fetchPromise

    expect(useSinksStore.getState().loading).toBe(false)
  })

  it('sets error on failure with envelope error', async () => {
    server.use(
      http.get('/api/v1/settings/observability/sinks', () =>
        HttpResponse.json(apiError('Network error')),
      ),
    )

    await useSinksStore.getState().fetchSinks()

    const state = useSinksStore.getState()
    expect(state.sinks).toHaveLength(0)
    expect(state.loading).toBe(false)
    expect(state.error).toBe('Network error')
  })

  it('sets generic error on HTTP 500 without envelope', async () => {
    server.use(
      http.get('/api/v1/settings/observability/sinks', () =>
        new HttpResponse('server exploded', { status: 500 }),
      ),
    )

    await useSinksStore.getState().fetchSinks()

    const state = useSinksStore.getState()
    // The store's getErrorMessage falls back to a generic label for
    // non-envelope error bodies.
    expect(state.error).not.toBeNull()
    expect(state.sinks).toHaveLength(0)
    expect(state.loading).toBe(false)
  })

  it('clears previous error on new fetch', async () => {
    useSinksStore.setState({ error: 'old error' })
    server.use(
      http.get('/api/v1/settings/observability/sinks', () =>
        HttpResponse.json(apiSuccess([makeSink()])),
      ),
    )

    await useSinksStore.getState().fetchSinks()

    expect(useSinksStore.getState().error).toBeNull()
  })
})

describe('testConfig', () => {
  it('forwards the request body to the backend and returns the result', async () => {
    const result: TestSinkResult = { valid: true, error: null }
    const requestBodies: unknown[] = []
    server.use(
      http.post(
        '/api/v1/settings/observability/sinks/_test',
        async ({ request }) => {
          requestBodies.push(await request.json())
          return HttpResponse.json(apiSuccess(result))
        },
      ),
    )

    const data = { sink_overrides: '{}', custom_sinks: '[]' }
    const response = await useSinksStore.getState().testConfig(data)

    expect(requestBodies).toHaveLength(1)
    expect(requestBodies[0]).toEqual(data)
    expect(response).toEqual(result)
  })

  it('returns null + emits error toast on testSinkConfig failure', async () => {
    server.use(
      http.post('/api/v1/settings/observability/sinks/_test', () =>
        HttpResponse.json(apiError('Invalid config')),
      ),
    )

    const data = { sink_overrides: '{}', custom_sinks: '[]' }
    const result = await useSinksStore.getState().testConfig(data)

    expect(result).toBeNull()
    expect(useSinksStore.getState().error).toBe('Invalid config')
    const errorToasts = useToastStore
      .getState()
      .toasts.filter((t) => t.variant === 'error')
    expect(errorToasts).toHaveLength(1)
    expect(errorToasts[0]!.title).toBe('Sink test failed')
  })
})
