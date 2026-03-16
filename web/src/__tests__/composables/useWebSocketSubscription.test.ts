import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { onMounted, onUnmounted } from 'vue'

// Mock Vue lifecycle hooks since we're not in a component context.
// onMounted callback is now async — we invoke it and store the promise
// so tests can await it when they need to verify post-connect behaviour.
let mountedPromise: Promise<void> | undefined
vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
    onMounted: vi.fn((cb: () => void | Promise<void>) => {
      const result = cb()
      if (result instanceof Promise) {
        mountedPromise = result // swallow — tests check via spies
      }
    }),
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
    mountedPromise = undefined
    vi.clearAllMocks()
    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    // Re-establish lifecycle mocks after clearAllMocks:
    // - onMounted: invokes callback (may be async); stores promise for awaiting
    // - onUnmounted: no-op recorder; getUnmountCallback() reads from mock.calls
    ;(onMounted as Mock).mockImplementation((cb: () => void | Promise<void>) => {
      const result = cb()
      if (result instanceof Promise) {
        mountedPromise = result
      }
    })
    ;(onUnmounted as Mock).mockImplementation(() => {})
  })

  function getUnmountCallback(): () => void {
    const calls = (onUnmounted as Mock).mock.calls
    expect(calls.length).toBeGreaterThan(0)
    return calls[calls.length - 1][0]
  }

  it('returns connected, reconnectExhausted, and setupError refs', () => {
    const handler: WsEventHandler = vi.fn()
    const result = useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(result.connected).toBeDefined()
    expect(result.reconnectExhausted).toBeDefined()
    expect(result.setupError).toBeDefined()
    expect(result.connected.value).toBe(false)
    expect(result.reconnectExhausted.value).toBe(false)
    expect(result.setupError.value).toBeNull()
  })

  it('calls connect when auth token exists and not connected', async () => {
    const connectSpy = vi.spyOn(wsStore, 'connect').mockResolvedValue()
    authStore.$patch({ token: 'test-token' })

    const handler: WsEventHandler = vi.fn()
    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })
    await mountedPromise

    expect(connectSpy).toHaveBeenCalledWith()
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

  it('skips all setup when no auth token', () => {
    const connectSpy = vi.spyOn(wsStore, 'connect')
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')

    const handler: WsEventHandler = vi.fn()
    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(connectSpy).not.toHaveBeenCalled()
    expect(subscribeSpy).not.toHaveBeenCalled()
    expect(onSpy).not.toHaveBeenCalled()
  })

  it('subscribes to deduplicated channels from bindings', async () => {
    vi.spyOn(wsStore, 'connect').mockResolvedValue()
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    authStore.$patch({ token: 'test-token' })
    const handler1: WsEventHandler = vi.fn()
    const handler2: WsEventHandler = vi.fn()

    useWebSocketSubscription({
      bindings: [
        { channel: 'tasks', handler: handler1 },
        { channel: 'budget', handler: handler2 },
      ],
    })
    await mountedPromise

    expect(subscribeSpy).toHaveBeenCalledWith(['tasks', 'budget'], undefined)
  })

  it('forwards filters to subscribe', async () => {
    vi.spyOn(wsStore, 'connect').mockResolvedValue()
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    authStore.$patch({ token: 'test-token' })
    const handler: WsEventHandler = vi.fn()
    const filters = { project: 'test-project' }

    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
      filters,
    })
    await mountedPromise

    expect(subscribeSpy).toHaveBeenCalledWith(['tasks'], filters)
  })

  it('calls onChannelEvent for each binding', async () => {
    vi.spyOn(wsStore, 'connect').mockResolvedValue()
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')
    authStore.$patch({ token: 'test-token' })
    const handler1: WsEventHandler = vi.fn()
    const handler2: WsEventHandler = vi.fn()

    useWebSocketSubscription({
      bindings: [
        { channel: 'tasks', handler: handler1 },
        { channel: 'budget', handler: handler2 },
      ],
    })
    await mountedPromise

    expect(onSpy).toHaveBeenCalledTimes(2)
    expect(onSpy).toHaveBeenCalledWith('tasks', handler1)
    expect(onSpy).toHaveBeenCalledWith('budget', handler2)
  })

  it('deduplicates channels but wires both handlers for same channel', async () => {
    vi.spyOn(wsStore, 'connect').mockResolvedValue()
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')
    authStore.$patch({ token: 'test-token' })
    const handler1: WsEventHandler = vi.fn()
    const handler2: WsEventHandler = vi.fn()

    useWebSocketSubscription({
      bindings: [
        { channel: 'tasks', handler: handler1 },
        { channel: 'tasks', handler: handler2 },
      ],
    })
    await mountedPromise

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
    authStore.$patch({ token: 'test-token' })
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

  it('sets setupError and logs when connect throws', () => {
    vi.spyOn(wsStore, 'connect').mockImplementation(() => {
      throw new Error('connection failed')
    })
    authStore.$patch({ token: 'test-token' })

    const handler: WsEventHandler = vi.fn()
    const { setupError } = useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    expect(setupError.value).toBe('WebSocket connection failed.')
    expect(consoleSpy).toHaveBeenCalledWith(
      'WebSocket connect failed:',
      'connection failed',
      expect.any(Error),
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

  it('sets setupError and logs when subscribe throws', async () => {
    vi.spyOn(wsStore, 'connect').mockResolvedValue()
    vi.spyOn(wsStore, 'subscribe').mockImplementation(() => {
      throw new Error('subscribe failed')
    })
    authStore.$patch({ token: 'test-token' })

    const handler: WsEventHandler = vi.fn()
    const { setupError } = useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })
    await mountedPromise

    expect(setupError.value).toBe('WebSocket subscription failed.')
    expect(consoleSpy).toHaveBeenCalledWith(
      'WebSocket subscribe failed:',
      'subscribe failed',
      expect.any(Error),
    )
  })

  it('still wires handlers when subscribe throws', async () => {
    vi.spyOn(wsStore, 'connect').mockResolvedValue()
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')
    vi.spyOn(wsStore, 'subscribe').mockImplementation(() => {
      throw new Error('subscribe failed')
    })
    authStore.$patch({ token: 'test-token' })

    const handler: WsEventHandler = vi.fn()
    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })
    await mountedPromise

    expect(onSpy).toHaveBeenCalledWith('tasks', handler)
  })

  it('handles empty bindings array with token', async () => {
    vi.spyOn(wsStore, 'connect').mockResolvedValue()
    const subscribeSpy = vi.spyOn(wsStore, 'subscribe')
    const onSpy = vi.spyOn(wsStore, 'onChannelEvent')
    authStore.$patch({ token: 'test-token' })

    const result = useWebSocketSubscription({ bindings: [] })
    await mountedPromise

    expect(subscribeSpy).toHaveBeenCalledWith([], undefined)
    expect(onSpy).not.toHaveBeenCalled()
    expect(result.connected.value).toBe(false)
  })

  it('unmount cleanup runs safely after failed connect', () => {
    const unsubscribeSpy = vi.spyOn(wsStore, 'unsubscribe')
    const offSpy = vi.spyOn(wsStore, 'offChannelEvent')
    vi.spyOn(wsStore, 'connect').mockImplementation(() => {
      throw new Error('connection failed')
    })
    authStore.$patch({ token: 'test-token' })

    const handler: WsEventHandler = vi.fn()
    useWebSocketSubscription({
      bindings: [{ channel: 'tasks', handler }],
    })

    const unmount = getUnmountCallback()
    unmount()

    // Cleanup runs even though setup failed
    expect(unsubscribeSpy).toHaveBeenCalledWith(['tasks'])
    expect(offSpy).toHaveBeenCalledWith('tasks', handler)
  })

  it.each(['connected', 'reconnectExhausted'] as const)(
    '%s ref reflects wsStore state',
    (refName) => {
      const handler: WsEventHandler = vi.fn()
      const result = useWebSocketSubscription({
        bindings: [{ channel: 'tasks', handler }],
      })

      expect(result[refName].value).toBe(false)
      wsStore.$patch({ [refName]: true })
      expect(result[refName].value).toBe(true)
    },
  )
})
