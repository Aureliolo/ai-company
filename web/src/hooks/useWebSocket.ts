import { useEffect, useRef, useState } from 'react'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'
import { sanitizeForLog } from '@/utils/logging'
import type { WsChannel, WsEventHandler, WsSubscriptionFilters } from '@/api/types'

/** A binding from a WebSocket channel to an event handler. */
export interface ChannelBinding {
  readonly channel: WsChannel
  readonly handler: WsEventHandler
}

/** Options for the useWebSocket hook. */
export interface WebSocketOptions {
  /** Channel-to-handler bindings. Each channel will be subscribed and its handler wired. */
  readonly bindings: readonly ChannelBinding[]
  /** Optional filters passed to wsStore.subscribe(). */
  readonly filters?: WsSubscriptionFilters
  /** Whether WebSocket should be active. Defaults to checking auth token. */
  readonly enabled?: boolean
}

/** Return type exposing WebSocket connection and setup status. */
export interface WebSocketReturn {
  /** Whether the WebSocket is currently connected. */
  readonly connected: boolean
  /** Whether reconnection attempts have been exhausted. */
  readonly reconnectExhausted: boolean
  /** Non-null when WebSocket setup failed (connect or subscribe error). */
  readonly setupError: string | null
}

/**
 * Manage WebSocket subscription lifecycle for a page view.
 *
 * Connects when enabled (default: auth token present), subscribes to
 * deduplicated channels, and wires event handlers on mount. Automatically
 * unsubscribes and removes handlers on unmount.
 */
export function useWebSocket(options: WebSocketOptions): WebSocketReturn {
  const { bindings, filters, enabled } = options
  const token = useAuthStore((s) => s.token)
  const connected = useWebSocketStore((s) => s.connected)
  const reconnectExhausted = useWebSocketStore((s) => s.reconnectExhausted)
  const [setupError, setSetupError] = useState<string | null>(null)
  const disposedRef = useRef(false)

  const isEnabled = enabled !== undefined ? enabled : !!token

  useEffect(() => {
    disposedRef.current = false

    if (!isEnabled) return

    const wsStore = useWebSocketStore.getState()
    const uniqueChannels: WsChannel[] = [...new Set(bindings.map((b) => b.channel))]

    const setup = async () => {
      try {
        if (!wsStore.connected) {
          await wsStore.connect()
        }
      } catch (err) {
        if (disposedRef.current) return
        setSetupError('WebSocket connection failed.')
        console.error('WebSocket connect failed:', sanitizeForLog(err))
        return
      }

      if (disposedRef.current) return

      try {
        wsStore.subscribe(uniqueChannels, filters)
      } catch (err) {
        setSetupError('WebSocket subscription failed.')
        console.error('WebSocket subscribe failed:', sanitizeForLog(err))
      }

      for (const binding of bindings) {
        try {
          wsStore.onChannelEvent(binding.channel, binding.handler)
        } catch (err) {
          console.error('WebSocket handler wiring failed:', sanitizeForLog(err))
        }
      }
    }

    setup()

    return () => {
      disposedRef.current = true
      try {
        wsStore.unsubscribe(uniqueChannels)
      } catch (err) {
        console.error('WebSocket unsubscribe failed:', sanitizeForLog(err))
      }
      for (const binding of bindings) {
        try {
          wsStore.offChannelEvent(binding.channel, binding.handler)
        } catch (err) {
          console.error('WebSocket handler cleanup failed:', sanitizeForLog(err))
        }
      }
    }
    // Bindings and filters are intentionally excluded -- they are captured once
    // on mount to match the Vue composable's lifecycle semantics. Changing them
    // requires remounting the component (e.g. via a key prop).
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [isEnabled])

  return { connected, reconnectExhausted, setupError }
}
