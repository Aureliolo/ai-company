import { renderHook, waitFor } from '@testing-library/react'
import { useAnalyticsStore } from '@/stores/analytics'
import { useDashboardData } from '@/hooks/useDashboardData'

const mockFetchDashboardData = vi.fn().mockResolvedValue(undefined)
const mockFetchOverview = vi.fn().mockResolvedValue(undefined)
const mockUpdateFromWsEvent = vi.fn()

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
    start: vi.fn(),
    stop: vi.fn(),
  }),
}))

function resetStore() {
  useAnalyticsStore.setState({
    overview: null,
    forecast: null,
    departmentHealths: [],
    activities: [],
    budgetConfig: null,
    orgHealthPercent: null,
    loading: false,
    error: null,
    fetchDashboardData: mockFetchDashboardData,
    fetchOverview: mockFetchOverview,
    updateFromWsEvent: mockUpdateFromWsEvent,
  })
}

describe('useDashboardData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetStore()
  })

  it('calls fetchDashboardData on mount', async () => {
    renderHook(() => useDashboardData())
    await waitFor(() => {
      expect(mockFetchDashboardData).toHaveBeenCalledTimes(1)
    })
  })

  it('returns loading state from store', () => {
    useAnalyticsStore.setState({ loading: true })
    const { result } = renderHook(() => useDashboardData())
    expect(result.current.loading).toBe(true)
  })

  it('returns overview from store', () => {
    const mockOverview = {
      total_tasks: 10, tasks_by_status: {} as never, total_agents: 5,
      total_cost_usd: 50, budget_remaining_usd: 450, budget_used_percent: 10,
      cost_7d_trend: [], active_agents_count: 3, idle_agents_count: 2,
    }
    useAnalyticsStore.setState({ overview: mockOverview })
    const { result } = renderHook(() => useDashboardData())
    expect(result.current.overview).toEqual(mockOverview)
  })

  it('returns error from store', () => {
    useAnalyticsStore.setState({ error: 'Something broke' })
    const { result } = renderHook(() => useDashboardData())
    expect(result.current.error).toBe('Something broke')
  })

  it('sets up WebSocket with 5 channel bindings', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    renderHook(() => useDashboardData())

    expect(useWebSocket).toHaveBeenCalledWith(
      expect.objectContaining({
        bindings: expect.arrayContaining([
          expect.objectContaining({ channel: 'tasks' }),
          expect.objectContaining({ channel: 'agents' }),
          expect.objectContaining({ channel: 'budget' }),
          expect.objectContaining({ channel: 'system' }),
          expect.objectContaining({ channel: 'approvals' }),
        ]),
      }),
    )
  })

  it('returns wsConnected from useWebSocket', () => {
    const { result } = renderHook(() => useDashboardData())
    expect(result.current.wsConnected).toBe(true)
  })

  it('starts polling on mount', async () => {
    const { usePolling } = await import('@/hooks/usePolling')
    const mockStart = vi.fn()
    vi.mocked(usePolling).mockReturnValue({
      active: false, error: null, start: mockStart, stop: vi.fn(),
    })

    renderHook(() => useDashboardData())
    await waitFor(() => {
      expect(mockStart).toHaveBeenCalled()
    })
  })
})
