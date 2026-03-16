import { computed, onMounted, onUnmounted, ref, type ComputedRef } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'
import { sanitizeForLog } from '@/utils/logging'
import type { WsChannel, WsEventHandler, WsSubscriptionFilters } from '@/api/types'

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
  readonly filters?: WsSubscriptionFilters
}

/** Return type exposing WebSocket connection and setup status. */
export interface WebSocketSubscriptionReturn {
  /** Whether the WebSocket is currently connected. */
  readonly connected: ComputedRef<boolean>
  /** Whether reconnection attempts have been exhausted. */
  readonly reconnectExhausted: ComputedRef<boolean>
  /** Non-null when WebSocket setup failed (connect or subscribe error). */
  readonly setupError: ComputedRef<string | null>
}

/**
 * Manage WebSocket subscription lifecycle for a page view.
 *
 * Connects when an auth token is available and no connection is active,
 * subscribes to deduplicated channels, and wires event handlers on mount.
 * Automatically unsubscribes and removes handlers on unmount.
 *
 * Channels are deduplicated for subscription — multiple bindings on the same
 * channel register multiple handlers but only one subscription.
 *
 * Setup errors (connect/subscribe failures) are caught and logged to console
 * but do not throw. Monitor `setupError` for a user-facing error message,
 * and `connected` / `reconnectExhausted` for connection health.
 *
 * When no auth token is present, all setup is skipped silently.
 */
export function useWebSocketSubscription(
  options: WebSocketSubscriptionOptions,
): WebSocketSubscriptionReturn {
  const wsStore = useWebSocketStore()
  const authStore = useAuthStore()
  const setupError = ref<string | null>(null)

  const uniqueChannels: WsChannel[] = [...new Set(options.bindings.map((b) => b.channel))]

  onMounted(() => {
    if (!authStore.token) return

    try {
      if (!wsStore.connected) {
        wsStore.connect(authStore.token)
      }
    } catch (err) {
      setupError.value = 'WebSocket connection failed.'
      console.error('WebSocket connect failed:', sanitizeForLog(err), err)
      return
    }

    try {
      wsStore.subscribe(uniqueChannels, options.filters)
    } catch (err) {
      setupError.value = 'WebSocket subscription failed.'
      console.error('WebSocket subscribe failed:', sanitizeForLog(err), err)
    }

    for (const binding of options.bindings) {
      try {
        wsStore.onChannelEvent(binding.channel, binding.handler)
      } catch (err) {
        console.error('WebSocket handler wiring failed:', sanitizeForLog(err), err)
      }
    }
  })

  onUnmounted(() => {
    try {
      wsStore.unsubscribe(uniqueChannels)
    } catch (err) {
      console.error('WebSocket unsubscribe failed:', sanitizeForLog(err), err)
    }
    for (const binding of options.bindings) {
      try {
        wsStore.offChannelEvent(binding.channel, binding.handler)
      } catch (err) {
        console.error('WebSocket handler cleanup failed:', sanitizeForLog(err), err)
      }
    }
  })

  return {
    connected: computed(() => wsStore.connected),
    reconnectExhausted: computed(() => wsStore.reconnectExhausted),
    setupError: computed(() => setupError.value),
  }
}
