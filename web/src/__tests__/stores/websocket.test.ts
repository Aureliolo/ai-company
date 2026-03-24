import { useWebSocketStore } from '@/stores/websocket'
import type { WsEvent } from '@/api/types'

// Mock the auth API for ticket exchange
vi.mock('@/api/endpoints/auth', () => ({
  getWsTicket: vi.fn(),
}))

// ── MockWebSocket ───────────────────────────────────────────

type WsListener = ((event: { data: string }) => void) | null

class MockWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  readonly CONNECTING = 0
  readonly OPEN = 1
  readonly CLOSING = 2
  readonly CLOSED = 3

  url: string
  readyState = MockWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  onmessage: WsListener = null
  sentMessages: string[] = []
  closed = false

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sentMessages.push(data)
  }

  close() {
    this.closed = true
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }

  // Test helpers
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }

  static instances: MockWebSocket[] = []
  static clear() {
    MockWebSocket.instances = []
  }
  static latest(): MockWebSocket | undefined {
    return MockWebSocket.instances[MockWebSocket.instances.length - 1]
  }
}

// Install MockWebSocket globally
const OriginalWebSocket = globalThis.WebSocket
beforeAll(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  globalThis.WebSocket = MockWebSocket as any
})
afterAll(() => {
  globalThis.WebSocket = OriginalWebSocket
})

function resetStore() {
  useWebSocketStore.getState().disconnect()
  useWebSocketStore.setState({
    connected: false,
    reconnectExhausted: false,
    subscribedChannels: [],
  })
  MockWebSocket.clear()
}

describe('websocket store', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('connect', () => {
    it('fetches ticket and creates WebSocket connection without ticket in URL', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()
      expect(ws).toBeDefined()
      // Ticket should NOT be in the URL (first-message auth)
      expect(ws!.url).not.toContain('ticket=')
    })

    it('sets connected to true on open', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      MockWebSocket.latest()!.simulateOpen()
      expect(useWebSocketStore.getState().connected).toBe(true)
    })

    it('deduplicates concurrent connect calls', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const p1 = useWebSocketStore.getState().connect()
      const p2 = useWebSocketStore.getState().connect()

      await vi.runAllTimersAsync()
      await Promise.all([p1, p2])

      expect(authApi.getWsTicket).toHaveBeenCalledTimes(1)
    })
  })

  describe('disconnect', () => {
    it('closes socket and resets state', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      useWebSocketStore.getState().disconnect()

      expect(ws.closed).toBe(true)
      expect(useWebSocketStore.getState().connected).toBe(false)
      expect(useWebSocketStore.getState().subscribedChannels).toEqual([])
    })
  })

  describe('subscribe', () => {
    it('sends subscribe message when connected', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      useWebSocketStore.getState().subscribe(['tasks', 'approvals'])

      const sent = ws.sentMessages.filter((m) => {
        const parsed = JSON.parse(m) as { action: string }
        return parsed.action === 'subscribe'
      })
      // One from auto-re-subscribe is not expected since we subscribed after open
      // The subscribe call itself should have sent one
      expect(sent.length).toBeGreaterThanOrEqual(1)
      const lastSub = JSON.parse(sent[sent.length - 1]!) as { channels: string[] }
      expect(lastSub.channels).toEqual(['tasks', 'approvals'])
    })

    it('queues subscription when not connected', () => {
      // Not connected, no socket
      useWebSocketStore.getState().subscribe(['tasks'])
      // No error thrown -- just queued
    })
  })

  describe('unsubscribe', () => {
    it('sends unsubscribe message when connected', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      useWebSocketStore.getState().subscribe(['tasks'])
      useWebSocketStore.getState().unsubscribe(['tasks'])

      const unsubMessages = ws.sentMessages.filter((m) => {
        const parsed = JSON.parse(m) as { action: string }
        return parsed.action === 'unsubscribe'
      })
      expect(unsubMessages).toHaveLength(1)
    })
  })

  describe('event dispatch', () => {
    it('dispatches events to channel handlers', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const handler = vi.fn()
      useWebSocketStore.getState().onChannelEvent('tasks', handler)

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      const event: WsEvent = {
        event_type: 'task.created',
        channel: 'tasks',
        timestamp: new Date().toISOString(),
        payload: { task_id: 'test-1' },
      }
      ws.simulateMessage(event)

      expect(handler).toHaveBeenCalledWith(event)
    })

    it('dispatches to wildcard handlers', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const wildcardHandler = vi.fn()
      useWebSocketStore.getState().onChannelEvent('*', wildcardHandler)

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      const event: WsEvent = {
        event_type: 'task.created',
        channel: 'tasks',
        timestamp: new Date().toISOString(),
        payload: {},
      }
      ws.simulateMessage(event)

      expect(wildcardHandler).toHaveBeenCalledWith(event)
    })

    it('removes handler with offChannelEvent', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const handler = vi.fn()
      useWebSocketStore.getState().onChannelEvent('tasks', handler)
      useWebSocketStore.getState().offChannelEvent('tasks', handler)

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      ws.simulateMessage({
        event_type: 'task.created',
        channel: 'tasks',
        timestamp: new Date().toISOString(),
        payload: {},
      })

      expect(handler).not.toHaveBeenCalled()
    })
  })

  describe('reconnection', () => {
    it('schedules reconnect on unexpected close', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      // Simulate unexpected close
      ws.simulateClose()
      expect(useWebSocketStore.getState().connected).toBe(false)

      // Advance timer to trigger reconnect (base delay = 1000ms)
      await vi.advanceTimersByTimeAsync(1000)

      // A new WebSocket should have been created
      expect(MockWebSocket.instances.length).toBeGreaterThan(1)
    })

    it('does not reconnect on intentional disconnect', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      const instanceCountBefore = MockWebSocket.instances.length
      useWebSocketStore.getState().disconnect()

      await vi.advanceTimersByTimeAsync(5000)

      // No new connections should be made
      expect(MockWebSocket.instances.length).toBe(instanceCountBefore)
    })
  })

  describe('message size gating', () => {
    it('discards oversized messages', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const handler = vi.fn()
      useWebSocketStore.getState().onChannelEvent('tasks', handler)

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      // Simulate oversized raw message (> 131072 chars)
      const oversized = 'x'.repeat(131073)
      ws.onmessage?.({ data: oversized })

      expect(handler).not.toHaveBeenCalled()
    })
  })

  describe('reconnect exhaustion', () => {
    it('sets reconnectExhausted after max attempts', async () => {
      const authApi = await import('@/api/endpoints/auth')
      // Ticket exchange always fails with non-401 error, triggering reconnect attempts
      vi.mocked(authApi.getWsTicket).mockRejectedValue(new Error('connection refused'))

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      // Each failed ticket exchange triggers scheduleReconnect
      // Advance through all 20 attempts (exponential backoff capped at 30s)
      for (let i = 0; i < 20; i++) {
        await vi.advanceTimersByTimeAsync(30_000)
        await vi.runAllTimersAsync()
      }

      expect(useWebSocketStore.getState().reconnectExhausted).toBe(true)
    })
  })

  describe('ticket 401 handling', () => {
    it('does not reconnect on ticket 401', async () => {
      const { AxiosError: Ae } = await import('axios')
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockRejectedValue(
        new Ae('Unauthorized', 'ERR_BAD_RESPONSE', undefined, undefined, {
          status: 401, data: {}, headers: {}, statusText: 'Unauthorized',
          config: {} as import('axios').AxiosResponse['config'],
        } as import('axios').AxiosResponse),
      )

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      // Advance time -- no reconnect should be scheduled on 401
      const instancesBefore = MockWebSocket.instances.length
      await vi.advanceTimersByTimeAsync(5000)
      expect(MockWebSocket.instances.length).toBe(instancesBefore)
    })
  })

  describe('first-message auth', () => {
    it('sends auth ticket as first message on open', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'my-secret-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      expect(ws.url).not.toContain('ticket=')

      ws.simulateOpen()

      // First message should be the auth action
      expect(ws.sentMessages.length).toBeGreaterThanOrEqual(1)
      const authMsg = JSON.parse(ws.sentMessages[0]!) as { action: string; ticket: string }
      expect(authMsg.action).toBe('auth')
      expect(authMsg.ticket).toBe('my-secret-ticket')
    })
  })

  describe('ack messages', () => {
    it('updates subscribedChannels on ack', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getWsTicket).mockResolvedValue({ ticket: 'test-ticket', expires_in: 30 })

      const connectPromise = useWebSocketStore.getState().connect()
      await vi.runAllTimersAsync()
      await connectPromise

      const ws = MockWebSocket.latest()!
      ws.simulateOpen()

      ws.simulateMessage({ action: 'subscribed', channels: ['tasks', 'approvals'] })
      expect(useWebSocketStore.getState().subscribedChannels).toEqual(['tasks', 'approvals'])
    })
  })
})
