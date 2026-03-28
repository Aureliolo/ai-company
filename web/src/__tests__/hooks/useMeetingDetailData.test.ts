import { renderHook, waitFor } from '@testing-library/react'
import { useMeetingsStore } from '@/stores/meetings'
import { useMeetingDetailData } from '@/hooks/useMeetingDetailData'
import { makeMeeting } from '../helpers/factories'

const mockFetchMeeting = vi.fn().mockResolvedValue(undefined)
const mockHandleWsEvent = vi.fn()

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({
    connected: true,
    reconnectExhausted: false,
    setupError: null,
  }),
}))

function resetStore() {
  useMeetingsStore.setState({
    selectedMeeting: null,
    loadingDetail: false,
    detailError: null,
    fetchMeeting: mockFetchMeeting,
    handleWsEvent: mockHandleWsEvent,
  })
}

describe('useMeetingDetailData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetStore()
  })

  it('calls fetchMeeting on mount with meetingId', async () => {
    renderHook(() => useMeetingDetailData('meeting-1'))
    await waitFor(() => {
      expect(mockFetchMeeting).toHaveBeenCalledWith('meeting-1')
    })
  })

  it('returns loading state from store', () => {
    useMeetingsStore.setState({ loadingDetail: true })
    const { result } = renderHook(() => useMeetingDetailData('meeting-1'))
    expect(result.current.loading).toBe(true)
  })

  it('returns meeting from store', () => {
    const meeting = makeMeeting('meeting-1')
    useMeetingsStore.setState({ selectedMeeting: meeting })
    const { result } = renderHook(() => useMeetingDetailData('meeting-1'))
    expect(result.current.meeting).toEqual(meeting)
  })

  it('returns error from store', () => {
    useMeetingsStore.setState({ detailError: 'Not found' })
    const { result } = renderHook(() => useMeetingDetailData('meeting-1'))
    expect(result.current.error).toBe('Not found')
  })

  it('sets up WebSocket with meetings channel', async () => {
    const { useWebSocket } = await import('@/hooks/useWebSocket')
    renderHook(() => useMeetingDetailData('meeting-1'))
    const calls = vi.mocked(useWebSocket).mock.calls
    expect(calls.length).toBeGreaterThan(0)
    const callArgs = calls[0]![0]
    const channels = callArgs.bindings.map((b) => b.channel)
    expect(channels).toEqual(['meetings'])
  })

  it('returns wsConnected from WebSocket hook', () => {
    const { result } = renderHook(() => useMeetingDetailData('meeting-1'))
    expect(result.current.wsConnected).toBe(true)
  })

  it('refetches when meetingId changes', async () => {
    const { rerender } = renderHook(
      ({ id }) => useMeetingDetailData(id),
      { initialProps: { id: 'meeting-1' } },
    )
    await waitFor(() => {
      expect(mockFetchMeeting).toHaveBeenCalledWith('meeting-1')
    })

    rerender({ id: 'meeting-2' })
    await waitFor(() => {
      expect(mockFetchMeeting).toHaveBeenCalledWith('meeting-2')
    })
  })
})
