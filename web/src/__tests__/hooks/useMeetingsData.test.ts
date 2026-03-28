import { renderHook, waitFor } from '@testing-library/react'
import { useMeetingsStore } from '@/stores/meetings'
import { useMeetingsData } from '@/hooks/useMeetingsData'
import { makeMeeting } from '../helpers/factories'

const mockFetchMeetings = vi.fn().mockResolvedValue(undefined)
const mockHandleWsEvent = vi.fn()
const mockTriggerMeeting = vi.fn().mockResolvedValue([])
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
  useMeetingsStore.setState({
    meetings: [],
    selectedMeeting: null,
    total: 0,
    loading: false,
    loadingDetail: false,
    error: null,
    detailError: null,
    triggering: false,
    fetchMeetings: mockFetchMeetings,
    handleWsEvent: mockHandleWsEvent,
    triggerMeeting: mockTriggerMeeting,
  })
}

describe('useMeetingsData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetStore()
  })

  it('calls fetchMeetings on mount', async () => {
    renderHook(() => useMeetingsData())
    await waitFor(() => {
      expect(mockFetchMeetings).toHaveBeenCalledTimes(1)
    })
  })

  it('returns loading state from store', () => {
    useMeetingsStore.setState({ loading: true })
    const { result } = renderHook(() => useMeetingsData())
    expect(result.current.loading).toBe(true)
  })

  it('returns meetings from store', () => {
    const items = [makeMeeting('1'), makeMeeting('2')]
    useMeetingsStore.setState({ meetings: items })
    const { result } = renderHook(() => useMeetingsData())
    expect(result.current.meetings).toHaveLength(2)
  })

  it('returns error from store', () => {
    useMeetingsStore.setState({ error: 'Connection lost' })
    const { result } = renderHook(() => useMeetingsData())
    expect(result.current.error).toBe('Connection lost')
  })

  it('starts polling on mount and stops on unmount', () => {
    const { unmount } = renderHook(() => useMeetingsData())
    expect(mockPollingStart).toHaveBeenCalledTimes(1)

    unmount()
    expect(mockPollingStop).toHaveBeenCalledTimes(1)
  })

  it('sets up WebSocket with meetings channel', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    renderHook(() => useMeetingsData())
    const callArgs = vi.mocked(useWebSocket).mock.calls[0]![0]
    const channels = callArgs.bindings.map((b) => b.channel)
    expect(channels).toEqual(['meetings'])
  })

  it('returns wsConnected from WebSocket hook', () => {
    const { result } = renderHook(() => useMeetingsData())
    expect(result.current.wsConnected).toBe(true)
  })

  it('returns total from store', () => {
    useMeetingsStore.setState({ total: 15 })
    const { result } = renderHook(() => useMeetingsData())
    expect(result.current.total).toBe(15)
  })

  it('returns triggering state from store', () => {
    useMeetingsStore.setState({ triggering: true })
    const { result } = renderHook(() => useMeetingsData())
    expect(result.current.triggering).toBe(true)
  })
})
