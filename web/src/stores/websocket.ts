/**
 * WebSocket connection state management (Zustand).
 *
 * Manages ticket-based auth, exponential backoff reconnection, channel-based
 * subscriptions with handler deduplication, and auto-re-subscribe on reconnect.
 */

import { create } from 'zustand'
import { AxiosError } from 'axios'
import type { WsChannel, WsEvent, WsEventHandler, WsSubscriptionFilters } from '@/api/types'
import { getWsTicket } from '@/api/endpoints/auth'
import { WS_RECONNECT_BASE_DELAY, WS_RECONNECT_MAX_DELAY, WS_MAX_RECONNECT_ATTEMPTS, WS_MAX_MESSAGE_SIZE } from '@/utils/constants'
import { sanitizeForLog } from '@/utils/logging'

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
  subscribedChannels: WsChannel[]

  connect: () => Promise<void>
  disconnect: () => void
  subscribe: (channels: WsChannel[], filters?: WsSubscriptionFilters) => void
  unsubscribe: (channels: WsChannel[]) => void
  onChannelEvent: (channel: WsChannel | '*', handler: WsEventHandler) => void
  offChannelEvent: (channel: WsChannel | '*', handler: WsEventHandler) => void
}

// ── Helpers ─────────────────────────────────────────────────

function getWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api/v1/ws`
}

function dispatchEvent(event: WsEvent) {
  channelHandlers.get(event.channel)?.forEach((h) => {
    try { h(event) } catch (err) {
      console.error('WebSocket channel handler error:', sanitizeForLog(err))
    }
  })
  channelHandlers.get('*')?.forEach((h) => {
    try { h(event) } catch (err) {
      console.error('WebSocket wildcard handler error:', sanitizeForLog(err))
    }
  })
}

// ── Store ───────────────────────────────────────────────────

export const useWebSocketStore = create<WebSocketState>()((set) => {
  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (reconnectAttempts >= WS_MAX_RECONNECT_ATTEMPTS) {
      console.error('WebSocket: max reconnection attempts reached')
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
          console.error('WebSocket reconnect failed:', sanitizeForLog(err))
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
      console.error('WebSocket ticket exchange failed:', sanitizeForLog(err))
      const isAuthError = err instanceof AxiosError && err.response?.status === 401
      if (shouldBeConnected && !isAuthError) {
        scheduleReconnect()
      }
      return
    }

    // Guard against stale connect attempts
    if (!shouldBeConnected || generation !== connectGeneration) {
      return
    }

    const url = `${getWsUrl()}?ticket=${encodeURIComponent(ticket)}`
    socket = new WebSocket(url)

    socket.onopen = () => {
      set({ connected: true })
      reconnectAttempts = 0
      pendingSubscriptions = []
      for (const sub of activeSubscriptions) {
        try {
          socket!.send(JSON.stringify({ action: 'subscribe', channels: sub.channels, filters: sub.filters }))
        } catch (err) {
          console.error('WebSocket subscribe send failed (will retry on reconnect):', sanitizeForLog(err))
        }
      }
    }

    socket.onmessage = (event: MessageEvent) => {
      if (typeof event.data === 'string' && event.data.length > WS_MAX_MESSAGE_SIZE) {
        console.error('WebSocket message exceeds max size, discarding')
        return
      }
      let data: unknown
      try {
        data = JSON.parse(event.data as string)
      } catch (parseErr) {
        console.error('Failed to parse WebSocket message:', sanitizeForLog(parseErr))
        return
      }

      const msg = data as Record<string, unknown>

      if (msg.action === 'subscribed' || msg.action === 'unsubscribed') {
        if (Array.isArray(msg.channels)) {
          set({ subscribedChannels: [...(msg.channels as WsChannel[])] })
        }
        return
      }

      if (msg.error) {
        console.error('WebSocket error:', sanitizeForLog(msg.error))
        return
      }

      if (msg.event_type && msg.channel) {
        try {
          dispatchEvent(msg as unknown as WsEvent)
        } catch (handlerErr) {
          console.error('WebSocket event handler error:', sanitizeForLog(handlerErr), 'Event type:', sanitizeForLog(msg.event_type, 100))
        }
      }
    }

    socket.onclose = () => {
      set({ connected: false })
      socket = null
      if (!intentionalClose && shouldBeConnected) {
        scheduleReconnect()
      }
    }

    socket.onerror = () => {
      console.error('WebSocket connection error')
    }
  }

  return {
    connected: false,
    reconnectExhausted: false,
    subscribedChannels: [],

    async connect() {
      if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return
      if (connectPromise) return connectPromise
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
        console.error('WebSocket subscribe send failed (queued for replay):', sanitizeForLog(err))
        if (!pendingSubscriptions.some((s) => subscriptionKey(s.channels, s.filters) === key)) {
          pendingSubscriptions.push({ channels, filters })
        }
      }
    },

    unsubscribe(channels: WsChannel[]) {
      const channelSet = new Set(channels)
      for (let i = activeSubscriptions.length - 1; i >= 0; i--) {
        if (activeSubscriptions[i]!.channels.every((c) => channelSet.has(c))) {
          activeSubscriptions.splice(i, 1)
        }
      }
      for (let i = pendingSubscriptions.length - 1; i >= 0; i--) {
        if (pendingSubscriptions[i]!.channels.every((c) => channelSet.has(c))) {
          pendingSubscriptions.splice(i, 1)
        }
      }

      if (!socket || socket.readyState !== WebSocket.OPEN) return
      try {
        socket.send(JSON.stringify({ action: 'unsubscribe', channels }))
      } catch (err) {
        console.error('WebSocket unsubscribe send failed:', sanitizeForLog(err))
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
