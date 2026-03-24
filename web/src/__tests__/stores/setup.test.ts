import { useSetupStore } from '@/stores/setup'

vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: vi.fn(),
}))

function resetStore() {
  useSetupStore.setState({
    setupComplete: null,
    loading: false,
  })
}

describe('setup store', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('initializes with null setupComplete and not loading', () => {
    const state = useSetupStore.getState()
    expect(state.setupComplete).toBeNull()
    expect(state.loading).toBe(false)
  })

  it('fetches setup status and sets setupComplete to true when needs_setup is false', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    vi.mocked(getSetupStatus).mockResolvedValue({
      needs_admin: false,
      needs_setup: false,
      has_providers: true,
      has_name_locales: true,
      has_company: true,
      has_agents: true,
      min_password_length: 12,
    })

    await useSetupStore.getState().fetchSetupStatus()

    const state = useSetupStore.getState()
    expect(state.setupComplete).toBe(true)
    expect(state.loading).toBe(false)
    expect(getSetupStatus).toHaveBeenCalledOnce()
  })

  it('fetches setup status and sets setupComplete to false when needs_setup is true', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    vi.mocked(getSetupStatus).mockResolvedValue({
      needs_admin: true,
      needs_setup: true,
      has_providers: false,
      has_name_locales: false,
      has_company: false,
      has_agents: false,
      min_password_length: 12,
    })

    await useSetupStore.getState().fetchSetupStatus()

    const state = useSetupStore.getState()
    expect(state.setupComplete).toBe(false)
    expect(state.loading).toBe(false)
  })

  it('prevents concurrent fetches', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    let resolveFirst: () => void
    const firstCall = new Promise<void>((r) => { resolveFirst = r })
    vi.mocked(getSetupStatus).mockImplementation(
      () => firstCall.then(() => ({
        needs_admin: false,
        needs_setup: false,
        has_providers: true,
        has_name_locales: true,
        has_company: true,
        has_agents: true,
        min_password_length: 12,
      })),
    )

    // Start first fetch
    const p1 = useSetupStore.getState().fetchSetupStatus()
    expect(useSetupStore.getState().loading).toBe(true)

    // Second fetch should be a no-op
    const p2 = useSetupStore.getState().fetchSetupStatus()

    resolveFirst!()
    await p1
    await p2

    expect(getSetupStatus).toHaveBeenCalledOnce()
  })

  it('leaves setupComplete as null on fetch error', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    vi.mocked(getSetupStatus).mockRejectedValue(new Error('Network error'))

    await useSetupStore.getState().fetchSetupStatus()

    const state = useSetupStore.getState()
    expect(state.setupComplete).toBeNull()
    expect(state.loading).toBe(false)
  })
})
