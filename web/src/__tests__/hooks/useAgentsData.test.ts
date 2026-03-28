import { renderHook, waitFor } from '@testing-library/react'
import { useAgentsStore } from '@/stores/agents'
import { useAgentsData } from '@/hooks/useAgentsData'
import { makeAgent } from '../helpers/factories'

const mockFetchAgents = vi.fn().mockResolvedValue(undefined)
const { mockPollingStart, mockPollingStop } = vi.hoisted(() => ({
  mockPollingStart: vi.fn(),
  mockPollingStop: vi.fn(),
}))

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({
    connected: true,
    reconnectExhausted: false,
    setupError: null,
  }),
}))

vi.mock('@/hooks/usePolling', () => ({
  usePolling: vi.fn().mockReturnValue({
    active: false,
    error: null,
    start: mockPollingStart,
    stop: mockPollingStop,
  }),
}))

function resetStore() {
  useAgentsStore.setState({
    agents: [],
    totalAgents: 0,
    listLoading: false,
    listError: null,
    searchQuery: '',
    departmentFilter: null,
    levelFilter: null,
    statusFilter: null,
    sortBy: 'name',
    sortDirection: 'asc',
    fetchAgents: mockFetchAgents,
  })
}

describe('useAgentsData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetStore()
  })

  it('calls fetchAgents on mount', async () => {
    renderHook(() => useAgentsData())
    await waitFor(() => {
      expect(mockFetchAgents).toHaveBeenCalledTimes(1)
    })
  })

  it('returns loading state from store', () => {
    useAgentsStore.setState({ listLoading: true })
    const { result } = renderHook(() => useAgentsData())
    expect(result.current.loading).toBe(true)
  })

  it('returns agents from store', () => {
    useAgentsStore.setState({ agents: [makeAgent('alice'), makeAgent('bob')] })
    const { result } = renderHook(() => useAgentsData())
    expect(result.current.agents).toHaveLength(2)
  })

  it('returns error from store', () => {
    useAgentsStore.setState({ listError: 'Network error' })
    const { result } = renderHook(() => useAgentsData())
    expect(result.current.error).toBe('Network error')
  })

  it('sets up WebSocket with 1 channel binding (agents)', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    renderHook(() => useAgentsData())

    const callArgs = vi.mocked(useWebSocket).mock.calls[0]![0]
    const channels = callArgs.bindings.map((b) => b.channel)
    expect(channels).toEqual(['agents'])
  })

  it('returns wsConnected from useWebSocket', () => {
    const { result } = renderHook(() => useAgentsData())
    expect(result.current.wsConnected).toBe(true)
  })

  it('returns wsConnected false when WebSocket disconnected', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    vi.mocked(useWebSocket).mockReturnValueOnce({
      connected: false,
      reconnectExhausted: false,
      setupError: null,
    })
    const { result } = renderHook(() => useAgentsData())
    expect(result.current.wsConnected).toBe(false)
  })

  it('returns wsSetupError from useWebSocket', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    vi.mocked(useWebSocket).mockReturnValueOnce({
      connected: false,
      reconnectExhausted: false,
      setupError: 'Auth failed',
    })
    const { result } = renderHook(() => useAgentsData())
    expect(result.current.wsSetupError).toBe('Auth failed')
  })

  it('starts polling on mount', async () => {
    renderHook(() => useAgentsData())
    await waitFor(() => {
      expect(mockPollingStart).toHaveBeenCalled()
    })
  })

  it('returns filtered agents based on store filters', () => {
    useAgentsStore.setState({
      agents: [
        makeAgent('alice', { department: 'engineering' }),
        makeAgent('bob', { department: 'product' }),
      ],
      departmentFilter: 'engineering',
    })
    const { result } = renderHook(() => useAgentsData())
    expect(result.current.filteredAgents).toHaveLength(1)
    expect(result.current.filteredAgents[0]!.name).toBe('alice')
  })
})
