import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { useMetaStore } from '@/stores/meta'
import { useToastStore } from '@/stores/toast'
import { apiError, apiSuccess } from '@/mocks/handlers'
import { server } from '@/test-setup'

function resetStore() {
  useMetaStore.setState({
    config: null,
    proposals: [],
    abTests: [],
    signals: null,
    loading: false,
    error: null,
    chatLoading: false,
  })
  useToastStore.setState({ toasts: [] })
}

beforeEach(() => {
  resetStore()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('fetchProposals', () => {
  it('stores proposals and clears error on success', async () => {
    server.use(
      http.get('/api/v1/meta/proposals', () =>
        HttpResponse.json(apiSuccess([])),
      ),
    )
    useMetaStore.setState({ error: 'stale' })

    await useMetaStore.getState().fetchProposals()

    expect(useMetaStore.getState().error).toBeNull()
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('sets error state on API failure without toasting (list-read pattern)', async () => {
    server.use(
      http.get('/api/v1/meta/proposals', () =>
        HttpResponse.json(apiError('boom')),
      ),
    )

    await useMetaStore.getState().fetchProposals()

    expect(useMetaStore.getState().error).toBe('boom')
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})

describe('fetchSignals', () => {
  it('stores signals and clears error on success', async () => {
    const response = { enabled: true, domains: [] as unknown[] }
    server.use(
      http.get('/api/v1/meta/signals', () =>
        HttpResponse.json(apiSuccess(response)),
      ),
    )
    useMetaStore.setState({ error: 'stale' })

    await useMetaStore.getState().fetchSignals()

    expect(useMetaStore.getState().error).toBeNull()
    expect(useMetaStore.getState().signals).toEqual(response)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('sets error state on API failure without toasting (list-read pattern)', async () => {
    server.use(
      http.get('/api/v1/meta/signals', () =>
        HttpResponse.json(apiError('boom')),
      ),
    )

    await useMetaStore.getState().fetchSignals()

    expect(useMetaStore.getState().error).toBe('boom')
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})

describe('sendChat', () => {
  it('returns the response on success', async () => {
    const response = { answer: 'hi', sources: [], confidence: 0.9 }
    const requestBodies: unknown[] = []
    server.use(
      http.post('/api/v1/meta/chat', async ({ request }) => {
        requestBodies.push(await request.json())
        return HttpResponse.json(apiSuccess(response))
      }),
    )

    const result = await useMetaStore.getState().sendChat('hello')

    expect(result).toEqual(response)
    expect(useMetaStore.getState().chatLoading).toBe(false)
    expect(requestBodies[0]).toEqual({ question: 'hello' })
  })

  it('returns null, sets error state, and emits an error toast on API failure', async () => {
    server.use(
      http.post('/api/v1/meta/chat', () =>
        HttpResponse.json(apiError('boom')),
      ),
    )

    const result = await useMetaStore.getState().sendChat('hello')

    expect(result).toBeNull()
    const state = useMetaStore.getState()
    expect(state.chatLoading).toBe(false)
    expect(state.error).toBe('boom')
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]!.variant).toBe('error')
    expect(toasts[0]!.title).toBe('Chat request failed')
    expect(toasts[0]!.description).toBe('boom')
  })

  it('clears chatLoading after success and failure', async () => {
    server.use(
      http.post('/api/v1/meta/chat', () =>
        HttpResponse.json(apiSuccess({ answer: 'ok', sources: [], confidence: 1 })),
      ),
    )
    await useMetaStore.getState().sendChat('q')
    expect(useMetaStore.getState().chatLoading).toBe(false)

    server.use(
      http.post('/api/v1/meta/chat', () =>
        HttpResponse.json(apiError('nope')),
      ),
    )
    await useMetaStore.getState().sendChat('q')
    expect(useMetaStore.getState().chatLoading).toBe(false)
  })
})
