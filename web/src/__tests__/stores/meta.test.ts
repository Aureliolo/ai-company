import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useMetaStore } from '@/stores/meta'
import { useToastStore } from '@/stores/toast'

vi.mock('@/api/endpoints/meta', () => ({
  getMetaConfig: vi.fn(),
  getSignals: vi.fn(),
  listABTests: vi.fn(),
  listProposals: vi.fn(),
  postChat: vi.fn(),
}))

async function importApi() {
  return await import('@/api/endpoints/meta')
}

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
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('fetchProposals', () => {
  it('stores proposals and clears error on success', async () => {
    const api = await importApi()
    useMetaStore.setState({ error: 'stale' })
    vi.mocked(api.listProposals).mockResolvedValue([])

    await useMetaStore.getState().fetchProposals()

    expect(useMetaStore.getState().error).toBeNull()
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('sets error state on API failure without toasting (list-read pattern)', async () => {
    const api = await importApi()
    vi.mocked(api.listProposals).mockRejectedValue(new Error('boom'))

    await useMetaStore.getState().fetchProposals()

    expect(useMetaStore.getState().error).toBe('boom')
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})

describe('fetchSignals', () => {
  it('stores signals and clears error on success', async () => {
    const api = await importApi()
    const response = { signals: [], collected_at: '2026-04-10T00:00:00Z' }
    useMetaStore.setState({ error: 'stale' })
    vi.mocked(api.getSignals).mockResolvedValue(
      response as unknown as Awaited<ReturnType<typeof api.getSignals>>,
    )

    await useMetaStore.getState().fetchSignals()

    expect(useMetaStore.getState().error).toBeNull()
    expect(useMetaStore.getState().signals).toEqual(response)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('sets error state on API failure without toasting (list-read pattern)', async () => {
    const api = await importApi()
    vi.mocked(api.getSignals).mockRejectedValue(new Error('boom'))

    await useMetaStore.getState().fetchSignals()

    expect(useMetaStore.getState().error).toBe('boom')
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})

describe('sendChat', () => {
  it('returns the response on success', async () => {
    const api = await importApi()
    const response = { answer: 'hi', sources: [], confidence: 0.9 }
    vi.mocked(api.postChat).mockResolvedValue(response)

    const result = await useMetaStore.getState().sendChat('hello')

    expect(result).toEqual(response)
    expect(useMetaStore.getState().chatLoading).toBe(false)
  })

  it('returns null, sets error state, and emits an error toast on API failure', async () => {
    const api = await importApi()
    vi.mocked(api.postChat).mockRejectedValue(new Error('boom'))

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
    const api = await importApi()
    vi.mocked(api.postChat).mockResolvedValue({ answer: 'ok', sources: [], confidence: 1 })
    await useMetaStore.getState().sendChat('q')
    expect(useMetaStore.getState().chatLoading).toBe(false)

    vi.mocked(api.postChat).mockRejectedValue(new Error('nope'))
    await useMetaStore.getState().sendChat('q')
    expect(useMetaStore.getState().chatLoading).toBe(false)
  })
})
