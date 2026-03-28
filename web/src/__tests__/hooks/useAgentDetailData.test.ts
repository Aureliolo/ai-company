import { renderHook, waitFor } from '@testing-library/react'
import { useAgentsStore } from '@/stores/agents'
import { useAgentDetailData } from '@/hooks/useAgentDetailData'
import { makeAgent, makeActivityEvent, makePerformanceSummary } from '../helpers/factories'

const mockFetchAgentDetail = vi.fn().mockResolvedValue(undefined)
const mockClearDetail = vi.fn()
const mockFetchMoreActivity = vi.fn().mockResolvedValue(undefined)
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
    selectedAgent: null,
    performance: null,
    agentTasks: [],
    activity: [],
    activityTotal: 0,
    activityLoading: false,
    careerHistory: [],
    detailLoading: false,
    detailError: null,
    fetchAgentDetail: mockFetchAgentDetail,
    clearDetail: mockClearDetail,
    fetchMoreActivity: mockFetchMoreActivity,
  })
}

describe('useAgentDetailData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetStore()
  })

  it('calls fetchAgentDetail on mount with agentName', async () => {
    renderHook(() => useAgentDetailData('alice'))
    await waitFor(() => {
      expect(mockFetchAgentDetail).toHaveBeenCalledWith('alice')
    })
  })

  it('calls clearDetail on unmount', () => {
    const { unmount } = renderHook(() => useAgentDetailData('alice'))
    unmount()
    expect(mockClearDetail).toHaveBeenCalled()
  })

  it('returns empty data when agentName is empty', () => {
    const { result } = renderHook(() => useAgentDetailData(''))
    expect(result.current.agent).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(result.current.wsConnected).toBe(false)
    expect(result.current.fetchMoreActivity).toBeTypeOf('function')
    expect(mockFetchAgentDetail).not.toHaveBeenCalled()
  })

  it('returns agent from store', () => {
    useAgentsStore.setState({ selectedAgent: makeAgent('alice') })
    const { result } = renderHook(() => useAgentDetailData('alice'))
    expect(result.current.agent?.name).toBe('alice')
  })

  it('returns loading and error from store', () => {
    useAgentsStore.setState({ detailLoading: true, detailError: 'Not found' })
    const { result } = renderHook(() => useAgentDetailData('alice'))
    expect(result.current.loading).toBe(true)
    expect(result.current.error).toBe('Not found')
  })

  it('sets up WebSocket with agents and tasks channels', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    renderHook(() => useAgentDetailData('alice'))

    const callArgs = vi.mocked(useWebSocket).mock.calls[0]![0]
    const channels = callArgs.bindings.map((b) => b.channel)
    expect(channels).toEqual(['agents', 'tasks'])
  })

  it('uses empty bindings when agentName is empty', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    renderHook(() => useAgentDetailData(''))

    const callArgs = vi.mocked(useWebSocket).mock.calls[0]![0]
    expect(callArgs.bindings).toHaveLength(0)
  })

  it('starts polling on mount', async () => {
    renderHook(() => useAgentDetailData('alice'))
    await waitFor(() => {
      expect(mockPollingStart).toHaveBeenCalled()
    })
  })

  it('does not start polling when agentName is empty', () => {
    renderHook(() => useAgentDetailData(''))
    expect(mockPollingStart).not.toHaveBeenCalled()
  })

  it('fetchMoreActivity passes activity.length as offset', () => {
    useAgentsStore.setState({
      activity: [makeActivityEvent(), makeActivityEvent()],
    })
    const { result } = renderHook(() => useAgentDetailData('alice'))
    result.current.fetchMoreActivity()
    expect(mockFetchMoreActivity).toHaveBeenCalledWith('alice', 2)
  })

  it('returns wsConnected from useWebSocket', () => {
    const { result } = renderHook(() => useAgentDetailData('alice'))
    expect(result.current.wsConnected).toBe(true)
  })

  it('computes performanceCards from store performance', () => {
    useAgentsStore.setState({
      selectedAgent: makeAgent('alice'),
      performance: makePerformanceSummary('alice'),
    })
    const { result } = renderHook(() => useAgentDetailData('alice'))
    expect(result.current.performanceCards).toHaveLength(4)
    expect(
      result.current.performanceCards.map((c) => c.label),
    ).toEqual([
      'TASKS COMPLETED',
      'AVG COMPLETION TIME',
      'SUCCESS RATE',
      'COST PER TASK',
    ])
  })

  it('computes insights from agent and performance', () => {
    useAgentsStore.setState({
      selectedAgent: makeAgent('alice'),
      performance: makePerformanceSummary('alice'),
    })
    const { result } = renderHook(() => useAgentDetailData('alice'))
    expect(result.current.insights).toHaveLength(2)
    expect(result.current.insights[0]).toContain('90.0%')
    expect(result.current.insights[1]).toContain('8.5')
  })

  it('returns wsConnected false when WebSocket disconnected', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    vi.mocked(useWebSocket).mockReturnValueOnce({
      connected: false,
      reconnectExhausted: false,
      setupError: null,
    })
    const { result } = renderHook(
      () => useAgentDetailData('alice'),
    )
    expect(result.current.wsConnected).toBe(false)
  })

  it('does not call store fetchMoreActivity when agentName empty', () => {
    const { result } = renderHook(() => useAgentDetailData(''))
    result.current.fetchMoreActivity()
    expect(mockFetchMoreActivity).not.toHaveBeenCalled()
  })
})
