import { computed, onMounted, onUnmounted, type ComputedRef } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'
import { sanitizeForLog } from '@/utils/logging'
import type { WsChannel, WsEventHandler } from '@/api/types'

/** A binding from a WebSocket channel to an event handler. */
export interface ChannelBinding {
  readonly channel: WsChannel
  readonly handler: WsEventHandler
}

/** Options for the useWebSocketSubscription composable. */
export interface WebSocketSubscriptionOptions {
  /** Channel-to-handler bindings. Each channel will be subscribed and its handler wired. */
  readonly bindings: readonly ChannelBinding[]
  /** Optional filters passed to wsStore.subscribe(). */
  readonly filters?: Record<string, string>
}

/** Return type exposing WebSocket connection status. */
export interface WebSocketSubscriptionReturn {
  /** Whether the WebSocket is currently connected. */
  readonly connected: ComputedRef<boolean>
  /** Whether reconnection attempts have been exhausted. */
  readonly reconnectExhausted: ComputedRef<boolean>
}

/**
 * Manage WebSocket subscription lifecycle for a page view.
 *
 * Connects (if needed), subscribes to channels, and wires event handlers on mount.
 * Automatically unsubscribes and removes handlers on unmount.
 */
export function useWebSocketSubscription(
  options: WebSocketSubscriptionOptions,
): WebSocketSubscriptionReturn {
  const wsStore = useWebSocketStore()
  const authStore = useAuthStore()

  const uniqueChannels: WsChannel[] = [...new Set(options.bindings.map((b) => b.channel))]

  onMounted(() => {
    try {
      if (authStore.token && !wsStore.connected) {
        wsStore.connect(authStore.token)
      }
      wsStore.subscribe(uniqueChannels, options.filters)
      for (const binding of options.bindings) {
        wsStore.onChannelEvent(binding.channel, binding.handler)
      }
    } catch (err) {
      console.error('WebSocket setup failed:', sanitizeForLog(err))
    }
  })

  onUnmounted(() => {
    wsStore.unsubscribe(uniqueChannels)
    for (const binding of options.bindings) {
      wsStore.offChannelEvent(binding.channel, binding.handler)
    }
  })

  return {
    connected: computed(() => wsStore.connected),
    reconnectExhausted: computed(() => wsStore.reconnectExhausted),
  }
}
