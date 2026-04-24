import { renderHook } from '@testing-library/react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'

function resetStores() {
  sessionStorage.clear()
  localStorage.clear()
  useAuthStore.setState({
    authStatus: 'unauthenticated',
    user: null,
    loading: false,
  })
  useWebSocketStore.getState().disconnect()
  useWebSocketStore.setState({
    connected: false,
    reconnectExhausted: false,
    subscribedChannels: [],
  })
}

describe('useWebSocket', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  it('does not connect when not authenticated', () => {
    const connectSpy = vi.spyOn(useWebSocketStore.getState(), 'connect')
    const handler = vi.fn()

    renderHook(() =>
      useWebSocket({
        bindings: [{ channel: 'tasks', handler }],
      }),
    )

    expect(connectSpy).not.toHaveBeenCalled()
  })

  it('connects and subscribes when authenticated', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useWebSocketStore.setState({ connected: true })

    const subscribeSpy = vi.spyOn(useWebSocketStore.getState(), 'subscribe')
    const onChannelSpy = vi.spyOn(
      useWebSocketStore.getState(),
      'onChannelEvent',
    )
    const handler = vi.fn()

    renderHook(() =>
      useWebSocket({
        bindings: [{ channel: 'tasks', handler }],
      }),
    )

    expect(subscribeSpy).toHaveBeenCalledWith(['tasks'], undefined)
    expect(onChannelSpy).toHaveBeenCalledWith('tasks', handler)
  })

  it('removes handlers AND unsubscribes channels on unmount', async () => {
    // Contract (updated per CodeRabbit review on PR #1545): cleanup
    // must remove per-handler registrations AND call wsStore.unsubscribe
    // for the channels the hook subscribed to. Before the fix, cleanup
    // only unwound handlers, leaking the channel subscriptions in the
    // store's subscribedChannels set and keeping stale traffic routed
    // to the unmounted view.
    useAuthStore.setState({ authStatus: 'authenticated' })
    useWebSocketStore.setState({ connected: true })

    const unsubscribeSpy = vi.spyOn(useWebSocketStore.getState(), 'unsubscribe')
    const offChannelSpy = vi.spyOn(
      useWebSocketStore.getState(),
      'offChannelEvent',
    )
    const handler = vi.fn()

    const { unmount } = renderHook(() =>
      useWebSocket({
        bindings: [{ channel: 'tasks', handler }],
      }),
    )

    // Let the effect's setup() promise chain settle so the subscribed
    // flag is flipped before we unmount. Without this the cleanup
    // races the setup and skips the unsubscribe.
    await Promise.resolve()
    await Promise.resolve()

    unmount()

    expect(offChannelSpy).toHaveBeenCalledWith('tasks', handler)
    expect(unsubscribeSpy).toHaveBeenCalledWith(['tasks'])
  })

  it('deduplicates channels from multiple bindings', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useWebSocketStore.setState({ connected: true })

    const subscribeSpy = vi.spyOn(useWebSocketStore.getState(), 'subscribe')
    const handler1 = vi.fn()
    const handler2 = vi.fn()

    renderHook(() =>
      useWebSocket({
        bindings: [
          { channel: 'tasks', handler: handler1 },
          { channel: 'tasks', handler: handler2 },
        ],
      }),
    )

    expect(subscribeSpy).toHaveBeenCalledWith(['tasks'], undefined)
  })

  it('skips setup when explicitly disabled', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    const connectSpy = vi.spyOn(useWebSocketStore.getState(), 'connect')
    const handler = vi.fn()

    renderHook(() =>
      useWebSocket({
        bindings: [{ channel: 'tasks', handler }],
        enabled: false,
      }),
    )

    expect(connectSpy).not.toHaveBeenCalled()
  })

  it('returns connection status from store', () => {
    useWebSocketStore.setState({ connected: true, reconnectExhausted: false })

    const handler = vi.fn()
    const { result } = renderHook(() =>
      useWebSocket({
        bindings: [{ channel: 'tasks', handler }],
        enabled: false,
      }),
    )

    expect(result.current.connected).toBe(true)
    expect(result.current.reconnectExhausted).toBe(false)
    expect(result.current.setupError).toBeNull()
  })
})
