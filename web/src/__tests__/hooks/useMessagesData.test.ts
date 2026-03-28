import { renderHook, waitFor } from '@testing-library/react'
import { useMessagesStore } from '@/stores/messages'
import { useMessagesData } from '@/hooks/useMessagesData'
import { useWebSocket } from '@/hooks/useWebSocket'
import { makeMessage, makeChannel } from '../helpers/factories'

const mockFetchChannels = vi.fn().mockResolvedValue(undefined)
const mockFetchMessages = vi.fn().mockResolvedValue(undefined)
const mockFetchMoreMessages = vi.fn().mockResolvedValue(undefined)
const mockResetUnread = vi.fn()
const mockHandleWsEvent = vi.fn()
const mockToggleThread = vi.fn()

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
  useMessagesStore.setState({
    channels: [],
    channelsLoading: false,
    channelsError: null,
    messages: [],
    total: 0,
    loading: false,
    loadingMore: false,
    error: null,
    unreadCounts: {},
    expandedThreads: new Set(),
    newMessageIds: new Set(),
    fetchChannels: mockFetchChannels,
    fetchMessages: mockFetchMessages,
    fetchMoreMessages: mockFetchMoreMessages,
    resetUnread: mockResetUnread,
    handleWsEvent: mockHandleWsEvent,
    toggleThread: mockToggleThread,
  })
}

describe('useMessagesData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetStore()
  })

  it('fetches channels on mount', async () => {
    renderHook(() => useMessagesData(null))
    await waitFor(() => {
      expect(mockFetchChannels).toHaveBeenCalledTimes(1)
    })
  })

  it('fetches messages when activeChannel is provided', async () => {
    renderHook(() => useMessagesData('#engineering'))
    await waitFor(() => {
      expect(mockFetchMessages).toHaveBeenCalledWith('#engineering')
    })
  })

  it('resets unread when activeChannel changes', async () => {
    renderHook(() => useMessagesData('#engineering'))
    await waitFor(() => {
      expect(mockResetUnread).toHaveBeenCalledWith('#engineering')
    })
  })

  it('does not fetch messages when activeChannel is null', () => {
    renderHook(() => useMessagesData(null))
    expect(mockFetchMessages).not.toHaveBeenCalled()
  })

  it('returns channels from store', () => {
    const channels = [makeChannel('#eng'), makeChannel('#product')]
    useMessagesStore.setState({ channels })
    const { result } = renderHook(() => useMessagesData(null))
    expect(result.current.channels).toHaveLength(2)
  })

  it('returns messages from store', () => {
    const msgs = [makeMessage('1'), makeMessage('2')]
    useMessagesStore.setState({ messages: msgs, total: 10 })
    const { result } = renderHook(() => useMessagesData('#eng'))
    expect(result.current.messages).toHaveLength(2)
    expect(result.current.total).toBe(10)
  })

  it('computes hasMore correctly', () => {
    useMessagesStore.setState({ messages: [makeMessage('1')], total: 5 })
    const { result } = renderHook(() => useMessagesData('#eng'))
    expect(result.current.hasMore).toBe(true)
  })

  it('computes hasMore as false when all loaded', () => {
    useMessagesStore.setState({ messages: [makeMessage('1')], total: 1 })
    const { result } = renderHook(() => useMessagesData('#eng'))
    expect(result.current.hasMore).toBe(false)
  })

  it('starts polling when channel is active', () => {
    renderHook(() => useMessagesData('#eng'))
    expect(mockPollingStart).toHaveBeenCalledTimes(1)
  })

  it('does not start polling when no channel', () => {
    renderHook(() => useMessagesData(null))
    expect(mockPollingStart).not.toHaveBeenCalled()
  })

  it('stops polling on unmount', () => {
    const { unmount } = renderHook(() => useMessagesData('#eng'))
    unmount()
    expect(mockPollingStop).toHaveBeenCalledTimes(1)
  })

  it('sets up WebSocket with messages channel', () => {
    renderHook(() => useMessagesData('#eng'))
    expect(vi.mocked(useWebSocket)).toHaveBeenCalled()
    const callArgs =
      vi.mocked(useWebSocket).mock.calls[0]![0]
    const channels =
      callArgs.bindings.map((b) => b.channel)
    expect(channels).toEqual(['messages'])
  })

  it('returns wsConnected from WebSocket hook', () => {
    const { result } = renderHook(() => useMessagesData(null))
    expect(result.current.wsConnected).toBe(true)
  })

  it('returns loading and error from store', () => {
    useMessagesStore.setState({ loading: true, error: 'oops' })
    const { result } = renderHook(() => useMessagesData('#eng'))
    expect(result.current.loading).toBe(true)
    expect(result.current.error).toBe('oops')
  })

  it('returns unreadCounts from store', () => {
    useMessagesStore.setState({ unreadCounts: { '#product': 3 } })
    const { result } = renderHook(() => useMessagesData('#eng'))
    expect(result.current.unreadCounts['#product']).toBe(3)
  })

  it('returns channelsLoading and channelsError', () => {
    useMessagesStore.setState({
      channelsLoading: true,
      channelsError: 'fail',
    })
    const { result } = renderHook(() => useMessagesData(null))
    expect(result.current.channelsLoading).toBe(true)
    expect(result.current.channelsError).toBe('fail')
  })

  it('returns loadingMore from store', () => {
    useMessagesStore.setState({ loadingMore: true })
    const { result } = renderHook(() => useMessagesData('#eng'))
    expect(result.current.loadingMore).toBe(true)
  })

  it('returns newMessageIds from store', () => {
    useMessagesStore.setState({
      newMessageIds: new Set(['msg-1']),
    })
    const { result } = renderHook(() => useMessagesData('#eng'))
    expect(result.current.newMessageIds.has('msg-1')).toBe(
      true,
    )
  })

  it('calls fetchMoreMessages via fetchMore', () => {
    const { result } = renderHook(() => useMessagesData('#eng'))
    result.current.fetchMore()
    expect(mockFetchMoreMessages).toHaveBeenCalledWith(
      '#eng',
    )
  })
})
