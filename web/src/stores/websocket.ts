/**
 * WebSocket connection state management (Zustand).
 *
 * Manages ticket-based auth, exponential backoff reconnection, channel-based
 * subscriptions with handler deduplication, and auto-re-subscribe on reconnect.
 */

import { create } from 'zustand'
import { AxiosError } from 'axios'
import { WS_CHANNELS } from '@/api/types'
import type { WsChannel, WsEvent, WsEventHandler, WsSubscriptionFilters } from '@/api/types'
import { getWsTicket } from '@/api/endpoints/auth'
import { WS_RECONNECT_BASE_DELAY, WS_RECONNECT_MAX_DELAY, WS_MAX_RECONNECT_ATTEMPTS, WS_MAX_MESSAGE_SIZE } from '@/utils/constants'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'

const log = createLogger('ws')

/** Build a stable deduplication key for a subscription (sorted channels + sorted filter keys). */
function subscriptionKey(channels: WsChannel[], filters?: Record<string, string>): string {
  const sortedChannels = [...channels].sort()
  const sortedFilters: Record<string, string> = {}
  if (filters) {
    for (const key of Object.keys(filters).sort()) {
      sortedFilters[key] = filters[key]!
    }
  }
  return JSON.stringify({ channels: sortedChannels, filters: sortedFilters })
}

// ── Module-scoped internals (not renderable state) ──────────

let socket: WebSocket | null = null
let reconnectAttempts = 0
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let intentionalClose = false
let shouldBeConnected = false
let connectPromise: Promise<void> | null = null
let connectGeneration = 0
const channelHandlers = new Map<string, Set<WsEventHandler>>()
let pendingSubscriptions: { channels: WsChannel[]; filters?: Record<string, string> }[] = []
const activeSubscriptions: { channels: WsChannel[]; filters?: Record<string, string> }[] = []

// ── Store types ─────────────────────────────────────────────

interface WebSocketState {
  connected: boolean
  reconnectExhausted: boolean
  subscribedChannels: readonly WsChannel[]

  connect: () => Promise<void>
  disconnect: () => void
  subscribe: (channels: WsChannel[], filters?: WsSubscriptionFilters) => void
  unsubscribe: (channels: WsChannel[]) => void
  onChannelEvent: (channel: WsChannel | '*', handler: WsEventHandler) => void
  offChannelEvent: (channel: WsChannel | '*', handler: WsEventHandler) => void
}

// ── Helpers ─────────────────────────────────────────────────

/** Known valid WsChannel values for runtime validation (derived from types.ts). */
const VALID_WS_CHANNELS: ReadonlySet<string> = new Set(WS_CHANNELS)

/** WS close codes that indicate auth failure (do not reconnect). */
const WS_AUTH_FAILURE_CODES = new Set([4001, 4003])

function getWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api/v1/ws`
}

/** Runtime validation that a parsed message conforms to the WsEvent shape. */
function isWsEvent(msg: Record<string, unknown>): msg is Record<string, unknown> & WsEvent {
  return (
    typeof msg.event_type === 'string' &&
    typeof msg.channel === 'string' &&
    typeof msg.timestamp === 'string' &&
    typeof msg.payload === 'object' &&
    msg.payload !== null &&
    !Array.isArray(msg.payload)
  )
}

/** Validate that a channels array from a server ack contains only known channel strings. */
function isWsChannelArray(arr: unknown): arr is WsChannel[] {
  return Array.isArray(arr) && arr.every((c) => typeof c === 'string' && VALID_WS_CHANNELS.has(c))
}

/** Estimate byte length of a string (accounts for multi-byte characters). */
function estimateByteLength(str: string): number {
  // TextEncoder gives accurate UTF-8 byte count
  return new TextEncoder().encode(str).byteLength
}

function dispatchEvent(event: WsEvent) {
  channelHandlers.get(event.channel)?.forEach((h) => {
    try { h(event) } catch (err) {
      log.error('Channel handler error:', err)
    }
  })
  channelHandlers.get('*')?.forEach((h) => {
    try { h(event) } catch (err) {
      log.error('Wildcard handler error:', err)
    }
  })
}

// ── Store ───────────────────────────────────────────────────

export const useWebSocketStore = create<WebSocketState>()((set) => {
  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (reconnectAttempts >= WS_MAX_RECONNECT_ATTEMPTS) {
      log.error('Max reconnection attempts reached')
      set({ reconnectExhausted: true })
      return
    }
    const delay = Math.min(
      WS_RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttempts),
      WS_RECONNECT_MAX_DELAY,
    )
    reconnectAttempts++
    reconnectTimer = setTimeout(() => {
      if (shouldBeConnected) {
        useWebSocketStore.getState().connect().catch((err) => {
          log.error('Reconnect failed:', err)
        })
      }
    }, delay)
  }

  async function doConnect(generation: number) {
    set({ reconnectExhausted: false })
    shouldBeConnected = true
    intentionalClose = false

    let ticket: string
    try {
      const resp = await getWsTicket()
      ticket = resp.ticket
    } catch (err) {
      log.error('Ticket exchange failed:', err)
      const isAuthError = err instanceof AxiosError && err.response?.status === 401
      if (shouldBeConnected && !isAuthError) {
        scheduleReconnect()
      }
      throw err
    }

    // Guard against stale connect attempts
    if (!shouldBeConnected || generation !== connectGeneration) {
      return
    }

    // First-message auth: connect without ticket in URL, send it as first message
    const url = getWsUrl()
    const thisSocket = new WebSocket(url)
    socket = thisSocket

    thisSocket.onopen = () => {
      // Guard: if a newer connection replaced us, bail out
      if (socket !== thisSocket) return

      // Send auth ticket as first message (keeps ticket out of URL/logs/history)
      try {
        thisSocket.send(JSON.stringify({ action: 'auth', ticket }))
      } catch (err) {
        log.error('Auth send failed:', err)
        thisSocket.close()
        return
      }

      // Note: connected is set before the server confirms the auth ticket.
      // If auth fails, onclose fires immediately with code 4001/4003 and
      // clears connected.  The brief true-then-false flash is inherent to
      // first-message auth (server must accept the upgrade to read the ticket).
      set({ connected: true })
      reconnectAttempts = 0
      pendingSubscriptions = []
      for (const sub of activeSubscriptions) {
        try {
          thisSocket.send(JSON.stringify({ action: 'subscribe', channels: sub.channels, filters: sub.filters }))
        } catch (err) {
          log.error('Subscribe send failed (will retry on reconnect):', err)
        }
      }
    }

    thisSocket.onmessage = (event: MessageEvent) => {
      if (typeof event.data !== 'string') return
      if (estimateByteLength(event.data) > WS_MAX_MESSAGE_SIZE) {
        log.error('Message exceeds max size, discarding')
        return
      }
      let data: unknown
      try {
        data = JSON.parse(event.data)
      } catch (parseErr) {
        log.error('Failed to parse message:', parseErr)
        return
      }

      if (typeof data !== 'object' || data === null || Array.isArray(data)) {
        log.error('Message is not a JSON object, discarding')
        return
      }

      const msg = data as Record<string, unknown>

      if (msg.action === 'subscribed' || msg.action === 'unsubscribed') {
        if (isWsChannelArray(msg.channels)) {
          set({ subscribedChannels: [...msg.channels] })
        }
        return
      }

      if (msg.error) {
        // Truncate attacker-controlled error value for log injection mitigation
        log.error('Server error:', sanitizeForLog(msg.error, 200))
        return
      }

      if (isWsEvent(msg)) {
        dispatchEvent(msg)
      } else {
        log.warn('Message failed WsEvent validation, discarding:', {
          hasEventType: typeof msg.event_type,
          hasChannel: typeof msg.channel,
          hasTimestamp: typeof msg.timestamp,
          hasPayload: typeof msg.payload,
        })
      }
    }

    thisSocket.onclose = (event: CloseEvent) => {
      // Guard: only act on our own socket, not a stale reference
      if (socket !== thisSocket) return
      set({ connected: false })
      socket = null

      // Auth failures (4001/4003): do not reconnect -- surface error
      if (WS_AUTH_FAILURE_CODES.has(event.code)) {
        log.error(`Auth failed (code ${event.code}):`, sanitizeForLog(event.reason, 200))
        set({ reconnectExhausted: true })
        return
      }

      if (!intentionalClose && shouldBeConnected) {
        scheduleReconnect()
      }
    }

    thisSocket.onerror = () => {
      log.error('Connection error', {
        url,
        readyState: thisSocket.readyState,
        reconnectAttempts,
      })
    }
  }

  return {
    connected: false,
    reconnectExhausted: false,
    subscribedChannels: [],

    async connect() {
      if (connectPromise) return connectPromise
      if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return
      const generation = connectGeneration
      connectPromise = doConnect(generation).finally(() => {
        if (generation === connectGeneration) connectPromise = null
      })
      return connectPromise
    },

    disconnect() {
      intentionalClose = true
      shouldBeConnected = false
      connectGeneration++
      connectPromise = null
      reconnectAttempts = 0
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      if (socket) {
        socket.close()
        socket = null
      }
      set({ connected: false, subscribedChannels: [] })
      pendingSubscriptions = []
      activeSubscriptions.length = 0
      channelHandlers.clear()
    },

    subscribe(channels: WsChannel[], filters?: WsSubscriptionFilters) {
      const key = subscriptionKey(channels, filters)
      if (!activeSubscriptions.some((s) => subscriptionKey(s.channels, s.filters) === key)) {
        activeSubscriptions.push({ channels: [...channels], filters: filters ? { ...filters } : undefined })
      }

      if (!socket || socket.readyState !== WebSocket.OPEN) {
        if (!pendingSubscriptions.some((s) => subscriptionKey(s.channels, s.filters) === key)) {
          pendingSubscriptions.push({ channels, filters })
        }
        return
      }
      try {
        socket.send(JSON.stringify({ action: 'subscribe', channels, filters }))
      } catch (err) {
        log.error('Subscribe send failed (queued for replay):', err)
        if (!pendingSubscriptions.some((s) => subscriptionKey(s.channels, s.filters) === key)) {
          pendingSubscriptions.push({ channels, filters })
        }
      }
    },

    unsubscribe(channels: WsChannel[]) {
      const channelSet = new Set(channels)
      // Remove matching channels from stored subscriptions and clean up empty entries
      for (let i = activeSubscriptions.length - 1; i >= 0; i--) {
        activeSubscriptions[i]!.channels = activeSubscriptions[i]!.channels.filter((c) => !channelSet.has(c))
        if (activeSubscriptions[i]!.channels.length === 0) {
          activeSubscriptions.splice(i, 1)
        }
      }
      for (let i = pendingSubscriptions.length - 1; i >= 0; i--) {
        pendingSubscriptions[i]!.channels = pendingSubscriptions[i]!.channels.filter((c) => !channelSet.has(c))
        if (pendingSubscriptions[i]!.channels.length === 0) {
          pendingSubscriptions.splice(i, 1)
        }
      }

      if (!socket || socket.readyState !== WebSocket.OPEN) return
      try {
        socket.send(JSON.stringify({ action: 'unsubscribe', channels }))
      } catch (err) {
        log.error('Unsubscribe send failed:', err)
      }
    },

    onChannelEvent(channel: WsChannel | '*', handler: WsEventHandler) {
      if (!channelHandlers.has(channel)) {
        channelHandlers.set(channel, new Set())
      }
      channelHandlers.get(channel)!.add(handler)
    },

    offChannelEvent(channel: WsChannel | '*', handler: WsEventHandler) {
      channelHandlers.get(channel)?.delete(handler)
    },
  }
})
