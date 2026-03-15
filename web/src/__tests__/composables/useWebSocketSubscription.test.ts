import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { onMounted, onUnmounted } from 'vue'

// Mock Vue lifecycle hooks since we're not in a component context
vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
    onMounted: vi.fn((cb: () => void) => cb()),
    onUnmounted: vi.fn(),
  }
})

import { useWebSocketSubscription } from '@/composables/useWebSocketSubscription'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'
import type { WsEventHandler } from '@/api/types'

describe('useWebSocketSubscription', () => {
  let wsStore: ReturnType<typeof useWebSocketStore>
  let authStore: ReturnType<typeof useAuthStore>
  let consoleSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsStore = useWebSocketStore()
    authStore = useAuthStore()
    vi.clearAllMocks()
    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    // Re-setup mocks cleared by clearAllMocks
    ;(onMounted as Mock).mockImplementation((cb: () => void) => cb())
  })

  function getUnmountCallback(): () => void {
    const calls = (onUnmounted as Mock).mock.calls
    expect(calls.length).toBeGreaterThan(0)
    return calls[calls.length - 1][0]
  }

  it('returns connected and reconnectExhausted refs', () => {
    const handler: WsEventHandler = vi.fn()
    const result = useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(result.connected).toBeDefined()
    expect(result.reconnectExhausted).toBeDefined()
    expect(result.connected.value).toBe(false)
    expect(result.reconnectExhausted.value).toBe(false)
  })

  it('calls connect when auth token exists and not connected', () => {
    const connectSpy = vi.spyOn(wsStore, 'connect')
    authStore.$patch({ token: 'test-token' })

    const handler: WsEventHandler = vi.fn()
    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(connectSpy).toHaveBeenCalledWith('test-token')
  })

  it('skips connect when already connected', () => {
    const connectSpy = vi.spyOn(wsStore, 'connect')
    authStore.$patch({ token: 'test-token' })
    wsStore.$patch({ connected: true })

    const handler: WsEventHandler = vi.fn()
    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(connectSpy).not.toHaveBeenCalled()
  })

  it('skips connect when no auth token', () => {
    const connectSpy = vi.spyOn(wsStore, 'connect')

    const handler: WsEventHandler = vi.fn()
    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(connectSpy).not.toHaveBeenCalled()
  })

  it('subscribes to deduplicated channels from bindings', () => {
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    const handler1: WsEventHandler = vi.fn()
    const handler2: WsEventHandler = vi.fn()

    useWebSocketSubscription({
      bindings: [
        { channel: 'tasks', handler: handler1 },
        { channel: 'budget', handler: handler2 },
      ],
    })

    expect(subscribeSpy).toHaveBeenCalledWith(['tasks', 'budget'], undefined)
  })

  it('forwards filters to subscribe', () => {
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    const handler: WsEventHandler = vi.fn()
    const filters = { project: 'test-project' }

    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
      filters,
    })

    expect(subscribeSpy).toHaveBeenCalledWith(['tasks'], filters)
  })

  it('calls onChannelEvent for each binding', () => {
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')
    const handler1: WsEventHandler = vi.fn()
    const handler2: WsEventHandler = vi.fn()

    useWebSocketSubscription({
      bindings: [
        { channel: 'tasks', handler: handler1 },
        { channel: 'budget', handler: handler2 },
      ],
    })

    expect(onSpy).toHaveBeenCalledTimes(2)
    expect(onSpy).toHaveBeenCalledWith('tasks', handler1)
    expect(onSpy).toHaveBeenCalledWith('budget', handler2)
  })

  it('deduplicates channels but wires both handlers for same channel', () => {
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')
    const handler1: WsEventHandler = vi.fn()
    const handler2: WsEventHandler = vi.fn()

    useWebSocketSubscription({
      bindings: [
        { channel: 'tasks', handler: handler1 },
        { channel: 'tasks', handler: handler2 },
      ],
    })

    // Subscribe only lists channel once
    expect(subscribeSpy).toHaveBeenCalledWith(['tasks'], undefined)
    // Both handlers wired
    expect(onSpy).toHaveBeenCalledTimes(2)
    expect(onSpy).toHaveBeenCalledWith('tasks', handler1)
    expect(onSpy).toHaveBeenCalledWith('tasks', handler2)
  })

  it('unsubscribes and removes handlers on unmount', () => {
    const unsubscribeSpy = vi.spyOn(wsStore, 'unsubscribe')
    const offSpy = vi.spyOn(wsStore, 'offChannelEvent')
    const handler1: WsEventHandler = vi.fn()
    const handler2: WsEventHandler = vi.fn()

    useWebSocketSubscription({
      bindings: [
        { channel: 'tasks', handler: handler1 },
        { channel: 'budget', handler: handler2 },
      ],
    })

    const unmount = getUnmountCallback()
    unmount()

    expect(unsubscribeSpy).toHaveBeenCalledWith(['tasks', 'budget'])
    expect(offSpy).toHaveBeenCalledTimes(2)
    expect(offSpy).toHaveBeenCalledWith('tasks', handler1)
    expect(offSpy).toHaveBeenCalledWith('budget', handler2)
  })

  it('swallows connect errors and logs them', () => {
    vi.spyOn(wsStore, 'connect').mockImplementation(() => {
      throw new Error('connection failed')
    })
    authStore.$patch({ token: 'test-token' })

    const handler: WsEventHandler = vi.fn()

    // Should not throw
    expect(() =>
      useWebSocketSubscription({
        bindings: [{ channel: 'tasks', handler }],
      }),
    ).not.toThrow()

    expect(consoleSpy).toHaveBeenCalledWith(
      'WebSocket setup failed:',
      expect.any(String),
    )
  })

  it('skips subscribe and handler wiring when connect throws', () => {
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')
    vi.spyOn(wsStore, 'connect').mockImplementation(() => {
      throw new Error('connection failed')
    })
    authStore.$patch({ token: 'test-token' })

    const handler: WsEventHandler = vi.fn()
    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(subscribeSpy).not.toHaveBeenCalled()
    expect(onSpy).not.toHaveBeenCalled()
  })

  it('swallows subscribe errors and logs them', () => {
    vi.spyOn(wsStore, 'subscribe').mockImplementation(() => {
      throw new Error('subscribe failed')
    })

    const handler: WsEventHandler = vi.fn()

    expect(() =>
      useWebSocketSubscription({
        bindings: [{ channel: 'tasks', handler }],
      }),
    ).not.toThrow()

    expect(consoleSpy).toHaveBeenCalledWith(
      'WebSocket setup failed:',
      expect.any(String),
    )
  })

  it('handles empty bindings array', () => {
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')

    const result = useWebSocketSubscription({ bindings: [] })

    expect(subscribeSpy).toHaveBeenCalledWith([], undefined)
    expect(onSpy).not.toHaveBeenCalled()
    expect(result.connected.value).toBe(false)
  })

  it('connected ref reflects wsStore.connected', () => {
    const handler: WsEventHandler = vi.fn()
    const { connected } = useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(connected.value).toBe(false)
    wsStore.$patch({ connected: true })
    expect(connected.value).toBe(true)
  })

  it('reconnectExhausted ref reflects wsStore.reconnectExhausted', () => {
    const handler: WsEventHandler = vi.fn()
    const { reconnectExhausted } = useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(reconnectExhausted.value).toBe(false)
    wsStore.$patch({ reconnectExhausted: true })
    expect(reconnectExhausted.value).toBe(true)
  })
})
