import { renderHook } from '@testing-library/react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/endpoints/auth', () => ({
  login: vi.fn(),
  setup: vi.fn(),
  getMe: vi.fn(),
  changePassword: vi.fn(),
  getWsTicket: vi.fn(),
}))

function resetStores() {
  sessionStorage.clear()
  localStorage.clear()
  useAuthStore.setState({ authStatus: 'unauthenticated', user: null, loading: false })
  useWebSocketStore.getState().disconnect()
  useWebSocketStore.setState({ connected: false, reconnectExhausted: false, subscribedChannels: [] })
}

describe('useWebSocket', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  it('does not connect when not authenticated', () => {
    const connectSpy = vi.spyOn(useWebSocketStore.getState(), 'connect')
    const handler = vi.fn()

    renderHook(() => useWebSocket({
      bindings: [{ channel: 'tasks', handler }],
    }))

    expect(connectSpy).not.toHaveBeenCalled()
  })

  it('connects and subscribes when authenticated', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    // Pre-set connected to avoid actual WebSocket
    useWebSocketStore.setState({ connected: true })

    const subscribeSpy = vi.spyOn(useWebSocketStore.getState(), 'subscribe')
    const onChannelSpy = vi.spyOn(useWebSocketStore.getState(), 'onChannelEvent')
    const handler = vi.fn()

    renderHook(() => useWebSocket({
      bindings: [{ channel: 'tasks', handler }],
    }))

    expect(subscribeSpy).toHaveBeenCalledWith(['tasks'], undefined)
    expect(onChannelSpy).toHaveBeenCalledWith('tasks', handler)
  })

  it('removes handlers on unmount (without global unsubscribe)', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useWebSocketStore.setState({ connected: true })

    const unsubscribeSpy = vi.spyOn(useWebSocketStore.getState(), 'unsubscribe')
    const offChannelSpy = vi.spyOn(useWebSocketStore.getState(), 'offChannelEvent')
    const handler = vi.fn()

    const { unmount } = renderHook(() => useWebSocket({
      bindings: [{ channel: 'tasks', handler }],
    }))

    unmount()

    // Should only remove handlers, NOT unsubscribe globally (other instances may share channels)
    expect(unsubscribeSpy).not.toHaveBeenCalled()
    expect(offChannelSpy).toHaveBeenCalledWith('tasks', handler)
  })

  it('deduplicates channels from multiple bindings', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useWebSocketStore.setState({ connected: true })

    const subscribeSpy = vi.spyOn(useWebSocketStore.getState(), 'subscribe')
    const handler1 = vi.fn()
    const handler2 = vi.fn()

    renderHook(() => useWebSocket({
      bindings: [
        { channel: 'tasks', handler: handler1 },
        { channel: 'tasks', handler: handler2 },
      ],
    }))

    // Subscribe should be called once with deduplicated channels
    expect(subscribeSpy).toHaveBeenCalledWith(['tasks'], undefined)
  })

  it('skips setup when explicitly disabled', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    const connectSpy = vi.spyOn(useWebSocketStore.getState(), 'connect')
    const handler = vi.fn()

    renderHook(() => useWebSocket({
      bindings: [{ channel: 'tasks', handler }],
      enabled: false,
    }))

    expect(connectSpy).not.toHaveBeenCalled()
  })

  it('returns connection status from store', () => {
    useWebSocketStore.setState({ connected: true, reconnectExhausted: false })

    const handler = vi.fn()
    const { result } = renderHook(() => useWebSocket({
      bindings: [{ channel: 'tasks', handler }],
      enabled: false,
    }))

    expect(result.current.connected).toBe(true)
    expect(result.current.reconnectExhausted).toBe(false)
    expect(result.current.setupError).toBeNull()
  })
})
